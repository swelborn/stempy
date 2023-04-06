#ifndef STEMPY_READER_ZMQ_H
#define STEMPY_READER_ZMQ_H

#include "reader.h"
#include <iostream>
#include <msgpack.hpp>
#include <pthread.h>
#include <sched.h>
#include <thread>
#include <vector>
#include <zmq.hpp>
#include <zmq_addon.hpp>

namespace stempy {

struct HeaderZMQ
{
  unsigned int scan_number = 0;
  unsigned int frame_number = 0;
  unsigned short nSTEM_positions_per_row_m1 = 0;
  unsigned short nSTEM_rows_m1 = 0;
  unsigned short STEM_x_position_in_row = 0;
  unsigned short STEM_row_in_scan = 0;
  unsigned short thread_id = 0;
  unsigned short module = 0;

  MSGPACK_DEFINE(scan_number, frame_number, nSTEM_positions_per_row_m1,
                 nSTEM_rows_m1, STEM_x_position_in_row, STEM_row_in_scan,
                 thread_id, module);
};

inline void print_memory_addresses(
  const std::vector<std::reference_wrapper<zmq::context_t>>& push_data_contexts)
{
  for (size_t i = 0; i < push_data_contexts.size(); ++i) {
    std::cout << "Address of context " << i << ": "
              << &push_data_contexts[i].get() << std::endl;
  }
}

inline void print_memory_address(
  const std::reference_wrapper<zmq::context_t>& push_data_context, int i)
{
  std::cout << "Address of context " << i << ": " << &push_data_context.get()
            << std::endl;
}

class ReaderZMQ : public SectorStreamThreadedReader
{
public:
  ReaderZMQ(std::vector<std::vector<std::reference_wrapper<zmq::context_t>>>&
              pull_data_contexts,
            zmq::context_t* pull_frame_info_context, uint8_t version = 5,
            int threads = 0);

  template <typename Functor>
  void process_frames(Functor& func, int i)
  {

    std::unique_ptr<ThreadPool> inner_pool = std::make_unique<ThreadPool>(1);
    std::vector<std::pair<int, std::future<void>>> inner_futures;

    cpu_set_t cpuset;
    CPU_ZERO(&cpuset);
    CPU_SET(i % std::thread::hardware_concurrency(), &cpuset);

    pthread_t current_thread = pthread_self();
    int ret =
      pthread_setaffinity_np(current_thread, sizeof(cpu_set_t), &cpuset);
    if (ret != 0) {
      std::cerr << "Error setting thread affinity: " << ret << std::endl;
      return;
    }

    std::unique_lock<std::mutex> pullSocketLock(m_pull_data_context_mutex);
    int group_index = i % m_pull_data_contexts.size();
    int socket_index = (i / m_pull_data_contexts.size()) %
                       m_pull_data_contexts[group_index].size();

    zmq::socket_t pull_socket(
      m_pull_data_contexts[group_index][socket_index].get(),
      zmq::socket_type::pull);
    pull_socket.set(zmq::sockopt::immediate, 1);

    pull_socket.connect(m_pull_data_addrs[group_index][socket_index]);
    std::cout << "Thread " << i << " connected to: "
              << m_pull_data_addrs[group_index][socket_index]
              << "\nSocket idx: " << socket_index
              << "\nGroup idx: " << group_index << std::endl;
    pullSocketLock.unlock();

    while (true) {

      if (m_num_msgs_counter >=
          m_scan_number_to_num_msgs[m_current_scan_number]) {
        std::cout << "inside break " << std::endl;
        std::cout << "hello " << std::endl;
        break;
      }
      zmq::message_t header_msg;
      bool header_received =
        pull_socket.recv(header_msg, zmq::recv_flags::dontwait);

      if (header_received) {
        // Read the header
        m_num_msgs_counter++;

        auto header = readHeader(header_msg);
        auto sector = header.sector;

        std::vector<Block> complete_blocks;
        auto pos = header.imageNumbers[0];
        auto frameNumber = header.frameNumber;
        if (m_num_msgs_counter % 10000 == 0) {
          std::cout << "num msgs counter " << m_num_msgs_counter << std::endl;
        }
        std::unique_lock<std::mutex> cacheLock(m_cacheMutex);
        auto& frame = m_frameCache[frameNumber];
        cacheLock.unlock();

        // Do we need to allocate the frame,use a double check lock
        if (std::atomic_load(&frame.block.data) == nullptr) {
          std::unique_lock<std::mutex> lock(frame.mutex);
          // Check again now we have the mutex
          if (std::atomic_load(&frame.block.data) == nullptr) {
            frame.block.header.version = version();
            frame.block.header.scanNumber = header.scanNumber;
            frame.block.header.scanDimensions = header.scanDimensions;
            frame.block.header.imagesInBlock = 1;
            frame.block.header.imageNumbers.push_back(pos);
            frame.block.header.frameNumber = frameNumber;
            frame.block.header.frameDimensions = FRAME_DIMENSIONS;
            frame.block.header.complete.resize(1);
            frame.block.header.complete[0] = false;
            std::shared_ptr<uint16_t> data;

            data.reset(new uint16_t[frame.block.header.frameDimensions.first *
                                    frame.block.header.frameDimensions.second],
                       std::default_delete<uint16_t[]>());
            std::fill(data.get(),
                      data.get() + frame.block.header.frameDimensions.first *
                                     frame.block.header.frameDimensions.second,
                      0);
            std::atomic_store(&frame.block.data, data);
          }
        }

        zmq::message_t data_msg;
        pull_socket.recv(data_msg, zmq::recv_flags::none);
        readSectorDataVersion5(data_msg, frame.block, sector);

        // Now now have the complete frame
        if (++frame.sectorCount == 4) {
          cacheLock.lock();
          frame.block.header.complete[0] = true;
          complete_blocks.emplace_back(frame.block);
          m_frameCache.erase(frameNumber);
          cacheLock.unlock();
        }

        // Finally call the function on any completed frames
        for (auto& b : complete_blocks) {
          inner_futures.emplace_back(
            std::make_pair(i, inner_pool->enqueue([&func, b, i]() mutable {
              // cpu_set_t cpuset;
              // CPU_ZERO(&cpuset);
              // CPU_SET(b.header.frameNumber %
              //           std::thread::hardware_concurrency(),
              //         &cpuset);
              // pthread_t current_thread = pthread_self();
              // int ret = pthread_setaffinity_np(current_thread,
              //                                  sizeof(cpu_set_t), &cpuset);
              // if (ret != 0) {
              //   std::cerr << "Error setting thread affinity: " << ret
              //             << std::endl;
              //   return;
              // }

              func(b);
              b.data.reset();
            })));
        }

        // Finally call the function on any completed frames
        // for (auto& b : complete_blocks) {
        // func(b);
        // }
      }
    }

    // TODO: Sleep helps this. Not sure why.
    // Wait for all the inner_futures to complete
    std::this_thread::sleep_for(std::chrono::seconds(3));

    bool all_futures_ready = false;
    size_t j = 0;
    while (!all_futures_ready) {
      all_futures_ready =
        true; // Assume all futures are ready until proven otherwise

      for (; j < inner_futures.size(); j++) {
        int thread_id = std::get<0>(inner_futures[j]);
        std::future<void>& future = std::get<1>(inner_futures[j]);
        std::future_status status =
          future.wait_for(std::chrono::milliseconds(1000));

        if (status == std::future_status::ready) {
          future.get();
          if (j + 1 == inner_futures.size()) {
            break;
          }
        } else {
          all_futures_ready = false; // At least one future is not ready
          std::cout << "Thread " << thread_id << " future " << (j + 1) << "of "
                    << inner_futures.size() << " is not ready" << std::endl;
          // std::this_thread::sleep_for(std::chrono::seconds(1));
          break;
        }
      }
      if (j == inner_futures.size()) {
        break;
      }
    }
    inner_pool.reset();
    std::cout << "Done thread " << i << std::endl;
    return;
  }

  template <typename Functor>
  std::future<void> readAll(Functor& func)
  {
    m_num_msgs_counter.store(0);
    m_pool = std::make_unique<ThreadPool>(m_threads);
    std::cout << "Creating worker threads" << std::endl;
    std::cout << "Num msgs_counter " << m_num_msgs_counter << std::endl;
    std::cout << "m_scan_number_to_num_msgs "
              << m_scan_number_to_num_msgs[m_current_scan_number] << std::endl;

    // Create worker threads
    for (int i = 0; i < m_threads; i++) {
      std::cout << "Creating worker thread " << i << std::endl;
      m_futures.emplace_back(
        m_pool->enqueue([this, &func, i]() { process_frames(func, i); }));
    }

    // std::this_thread::sleep_for(std::chrono::seconds(5));
    // Return a future that is resolved once the processing is complete
    auto complete = std::async(std::launch::async, [this]() {
      for (auto& future : this->m_futures) {
        future.get();
        std::cout << "Got a future from readAll" << std::endl;
      }
    });
    std::cout << "About to return complete" << std::endl;
    return complete;
  }

  Header readHeader(zmq::message_t& header_msg);
  void setup_sockets();
  void readSectorDataVersion5(zmq::message_t& data_msg, Block& block,
                              int sector);

  void pull_frame_info();
  std::map<unsigned int, unsigned int> m_scan_number_to_num_msgs;
  unsigned int m_current_scan_number = 0;
  std::mutex m_pull_data_context_mutex;

private:
  std::vector<std::vector<std::reference_wrapper<zmq::context_t>>>&
    m_pull_data_contexts;
  zmq::context_t* m_pull_frame_info_context;
  std::unique_ptr<zmq::socket_t> m_pull_frame_info_socket;
  std::vector<std::unique_ptr<zmq::socket_t>> m_pull_data_sockets;
  std::vector<std::vector<std::string>> m_pull_data_addrs;

  uint8_t m_version;
  std::atomic<size_t> m_num_msgs_counter{ 0 };
};
} // namespace stempy
#endif /* STEMPY_READER_ZMQ_H */
