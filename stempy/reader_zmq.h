#ifndef STEMPY_READER_ZMQ_H
#define STEMPY_READER_ZMQ_H

#include "reader.h"
#include <condition_variable>
#include <iostream>
#include <msgpack.hpp>
#include <pthread.h>
#include <sched.h>
#include <thread>
#include <vector>
#include <zmq.hpp>
#include <zmq_addon.hpp>

namespace stempy {

/**
 * @brief ReaderZMQ class for multi-threaded frame processing from NodeGroups.
 *
 * This class extends the SectorStreamThreadedReader and provides a specific
 * implementation for processing STEM frames from NodeGroups.
 *
 * It uses multiple threads to process frames and manage resources.
 */
class ReaderZMQ : public SectorStreamThreadedReader
{
public:
  std::map<unsigned int, unsigned int> m_scan_number_to_num_msgs;
  unsigned int m_current_scan_number = 0;
  std::mutex m_pull_data_context_mutex;

private:
  std::vector<std::vector<std::shared_ptr<zmq::context_t>>>&
    m_pull_data_contexts;
  zmq::context_t* m_pull_frame_info_context;
  std::unique_ptr<zmq::socket_t> m_pull_frame_info_socket;
  std::vector<std::unique_ptr<zmq::socket_t>> m_pull_data_sockets;
  std::vector<std::vector<std::string>> m_pull_data_addrs;
  uint8_t m_version;
  std::atomic<size_t> m_num_msgs_counter{ 0 };
  std::mutex m_thread_synchronization_mutex;
  std::condition_variable m_release_threads_cv;
  std::atomic<int> m_finished_threads{ 0 };

  /**
   * @brief Reads and processes header data from a received ZeroMQ message.
   *
   * Extracts the header information from the given ZeroMQ message, deserializes
   * it using msgpack, and returns a stempy::Header struct.
   *
   * @param header_msg A reference to a zmq::message_t containing the header
   * data.
   * @return A Header struct containing the header data.
   */
  Header readHeader(zmq::message_t& header_msg);

  /**
   * @brief Sets up the pull data addresses for the ReaderZMQ.
   *
   * Configures the pull data addresses that will be used to receive data from
   * the NodeGroups. The addresses are in the format "inproc://<index>",
   * where the index is calculated based on the node_group_number and
   * socket_idx_in_node_group.
   */
  void setup_pull_data_addrs();

  /**
   * @brief Sets up the ZeroMQ sockets for receiving data.
   *
   * Initializes the ZeroMQ sockets used to receive data from the NodeGroups.
   * Configures sockets for receiving frame information and sector data for each
   * thread.
   */
  void setup_sockets();

  /**
   * @brief Reads and processes sector data from a received ZeroMQ message
   * (version 5).
   *
   * Extracts and processes the sector data from the given ZeroMQ message and
   * updates the Block struct with the received data.
   *
   * @param data_msg A reference to a zmq::message_t containing the sector data.
   * @param block A reference to a Block struct that will be updated with the
   * sector data.
   * @param sector The sector number.
   */
  void readSectorDataVersion5(zmq::message_t& data_msg, Block& block,
                              int sector);

public:
  /**
   * @brief ReaderZMQ constructor.
   *
   * Contexts are passed in from Nodes.cpp, necessary because inproc requires
   * the same context for inproc. NodeGroups also contain these contexts.
   *
   * @param pull_data_contexts A reference to a vector of vectors containing
   * shared_ptr<zmq::context_t>.
   * @param pull_frame_info_context A pointer to a zmq::context_t object for
   * pulling frame information.
   * @param version The version number for the data format, defaults to 5.
   * @param threads The number of threads to use for processing, defaults to 0.
   */
  ReaderZMQ(std::vector<std::vector<std::shared_ptr<zmq::context_t>>>&
              pull_data_contexts,
            zmq::context_t* pull_frame_info_context, uint8_t version = 5,
            int threads = 0);

  /**
   * @brief Pulls frame information from the NodeGroups.
   *
   * Retrieves and processes frame information from the NodeGroups by
   * receiving a message containing the scan number to frame count mapping.
   * Updates the m_scan_number_to_num_msgs map with the received data.
   */
  void pull_frame_info();

  /**
   * @brief Implements a barrier synchronization primitive for multithreading.
   *
   * This function is called by multiple threads to ensure that all threads
   * reach a certain point in their execution before any of them proceed.
   *
   * When the last thread arrives at the barrier, the barrier count is reset
   * and all waiting threads are notified to continue.
   *
   * NOTE: copied from 4dstem repo.
   */
  void barrier(std::string msg = "")
  {
    std::unique_lock<std::mutex> lock(m_thread_synchronization_mutex);
    m_finished_threads++;

    if (m_finished_threads == m_threads) {
      std::cout << msg << std::endl;
      m_finished_threads = 0; // Reset the count for the next barrier
      m_release_threads_cv.notify_all();
    } else {
      m_release_threads_cv.wait(lock,
                                [this] { return m_finished_threads == 0; });
    }
  }

  /**
   * @brief Processes frames sent by NodeGroups using the given functor.
   *
   * Reads frames from NodeGroups processes them using the provided functor.
   * This function runs on m_threads, and uses m_frame_cache to share all frames
   * received across the threads.
   *
   * Once the number of expected frames is reached, receiving loop is broken in
   * all threads, and continues to run the enqueued functor, along with the
   * remaining incomplete frames in the cache.
   *
   * @tparam Functor The type of the processing functor.
   * @param func The processing functor. electronCount is used.
   * @param pull_socket A reference to the ZeroMQ pull socket used to receive
   * data.
   * @param i The index of the pull_socket, also used to set thread affinity.
   */
  template <typename Functor>
  void process_frames(Functor& func, zmq::socket_t& pull_socket, int i)
  {
    // Create a single-threaded pool for inner processing
    std::unique_ptr<ThreadPool> inner_pool = std::make_unique<ThreadPool>(1);
    std::vector<std::pair<int, std::future<void>>> inner_futures;

    // TODO: remove this
    // This was used to create pull sockets in each thread. I thought it was a
    // bottleneck, but I don't think that was the case. Leaving here for now,
    // just in case.

    // std::unique_lock<std::mutex>
    // pullSocketLock(m_pull_data_context_mutex); int group_index = i %
    // m_pull_data_contexts.size(); int socket_index = (i /
    // m_pull_data_contexts.size()) %
    //                    m_pull_data_contexts[group_index].size();

    // Create a new pull data socket and assign it to the appropriate index
    // m_pull_data_sockets[i] = std::make_unique<zmq::socket_t>(
    //   (*m_pull_data_contexts[group_index][socket_index]),
    //   zmq::socket_type::pull);
    // (*m_pull_data_sockets[i])
    //   .connect(m_pull_data_addrs[group_index][socket_index]);

    // zmq::socket_t pull_socket(
    //   (*m_pull_data_contexts[group_index][socket_index]),
    //   zmq::socket_type::pull);
    // pull_socket.set(zmq::sockopt::immediate, 1);

    // pull_socket.connect(m_pull_data_addrs[group_index][socket_index]);
    // // std::cout << "Thread " << i << " connected to: "
    // //           << m_pull_data_addrs[group_index][socket_index]
    // //           << "\nSocket idx: " << socket_index
    // //           << "\nGroup idx: " << group_index << std::endl;
    // pullSocketLock.unlock();

    // Main loop for processing frames
    while (true) {
      // Check if all messages have been processed
      if (m_num_msgs_counter >=
          m_scan_number_to_num_msgs[m_current_scan_number]) {
        break;
      }

      // Receive header message
      zmq::message_t header_msg;
      bool header_received =
        pull_socket.recv(header_msg, zmq::recv_flags::dontwait);

      // Process header and corresponding data message
      if (header_received) {
        m_num_msgs_counter++;
        if (m_num_msgs_counter % 10000 == 0) {
          std::cout << "num msgs counter " << m_num_msgs_counter << std::endl;
        }

        auto header = readHeader(header_msg);
        auto sector = header.sector;
        auto pos = header.imageNumbers[0];
        auto frameNumber = header.frameNumber;

        // Lock frame cache and get frame from it
        std::unique_lock<std::mutex> cacheLock(m_cacheMutex);
        auto& frame = m_frameCache[frameNumber];
        cacheLock.unlock();

        // Initialize frame data if it's not already initialized
        if (std::atomic_load(&frame.block.data) == nullptr) {
          std::unique_lock<std::mutex> lock(frame.mutex);
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

        // Receive data message and process sector data
        zmq::message_t data_msg;
        pull_socket.recv(data_msg, zmq::recv_flags::none);
        readSectorDataVersion5(data_msg, frame.block, sector);

        // Check if the frame is complete
        std::vector<Block> complete_blocks;
        if (++frame.sectorCount == 4) {
          cacheLock.lock();
          frame.block.header.complete[0] = true;
          complete_blocks.emplace_back(frame.block);
          m_frameCache.erase(frameNumber);
          cacheLock.unlock();
        }

        // Call function on any completed frames
        for (auto& b : complete_blocks) {
          inner_futures.emplace_back(
            std::make_pair(i, inner_pool->enqueue([&func, b, i]() mutable {
              func(b);
              b.data.reset();
            })));
        }
      }
    }

    if (i == 0) {
      std::cout << "Done receiving data." << std::endl;
    }

    // Synchronize threads before entering the while loop
    barrier("Synchronized threads after receiving data.");

    // Check if all inner futures are ready
    // TODO: this is likely not necessary, could probably be done by a
    // futures.wait() or something - this was originally written to debug a
    // problem that was fixed upstream (header was not being sent properly).
    bool all_futures_ready = false;
    size_t j = 0;
    while (!all_futures_ready) {
      all_futures_ready =
        true; // Assume all futures are ready until proven otherwise

      for (; j < inner_futures.size(); j++) {
        int thread_id = std::get<0>(inner_futures[j]);
        std::future<void>& future = std::get<1>(inner_futures[j]);
        std::future_status status =
          future.wait_for(std::chrono::milliseconds(100));

        if (status == std::future_status::ready) {
          future.get();
          if (j + 1 == inner_futures.size()) {
            break;
          }
        } else {
          all_futures_ready = false; // At least one future is not ready
          std::cout << "Thread " << thread_id << " future " << (j + 1) << "of "
                    << inner_futures.size() << " is not ready" << std::endl;
          break;
        }
      }
      if (j == inner_futures.size()) {
        break;
      }
    }

    // Process incomplete blocks
    bool more_frames = true;
    while (more_frames) {
      std::unique_lock<std::mutex> cacheLock(m_cacheMutex);
      auto frame_it = m_frameCache.begin();
      if (frame_it != m_frameCache.end()) {
        Block block = frame_it->second.block;
        m_frameCache.erase(frame_it);
        cacheLock.unlock();

        func(block);
        block.data.reset();
      } else {
        more_frames = false;
      }
    }

    // Synchronize threads before exiting
    barrier("Synchronized threads after processing incomplete frames.");

    return;
  }

  /**
   * @brief Reads all data from the NodeGroups and processes it using the given
   * functor.
   *
   * Sets up the thread pool, processes data from the NodeGroups, and processes
   * it using the given functor. Returns a future that resolves when all
   * processing is complete.
   *
   * @tparam Functor The type of the processing functor.
   * @param func The processing functor.
   * @return A future that resolves when all processing is complete.
   */
  template <typename Functor>
  std::future<void> readAll(Functor& func)
  {
    m_num_msgs_counter.store(0);
    m_pool = std::make_unique<ThreadPool>(m_threads);
    std::cout << "Number of expected frames on reader: "
              << m_scan_number_to_num_msgs[m_current_scan_number] << std::endl;

    // Create worker threads
    for (int i = 0; i < m_threads; i++) {
      m_futures.emplace_back(m_pool->enqueue([this, &func, i]() {
        // Set thread affinity for the current thread
        cpu_set_t cpuset;
        CPU_ZERO(&cpuset);

        // Round robin to all cores
        CPU_SET(i % std::thread::hardware_concurrency(), &cpuset);
        pthread_t current_thread = pthread_self();
        int ret =
          pthread_setaffinity_np(current_thread, sizeof(cpu_set_t), &cpuset);
        if (ret != 0) {
          std::cerr << "Error setting thread affinity: " << ret << std::endl;
          return;
        }
        process_frames(func, *m_pull_data_sockets[i], i);
      }));
    }

    // Return a future that is resolved once the processing is complete
    auto complete = std::async(std::launch::async, [this]() {
      for (auto& future : this->m_futures) {
        future.get();
      }
    });
    return complete;
  }
};
} // namespace stempy
#endif /* STEMPY_READER_ZMQ_H */
