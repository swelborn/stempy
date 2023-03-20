#include "reader_zmq.h"
#include "reader.h"
#include <msgpack.hpp>
#include <zmq.hpp>

namespace stempy {
ReaderZMQ::ReaderZMQ(zmq::context_t* context, uint8_t version = 5,
                     int threads = 0)
  : SectorStreamThreadedReader("", version, threads), m_context(context), m_version(version)
{
  setup_sockets();
}

void ReaderZMQ::setup_sockets()
{
  m_pull_socket_data =
    std::make_unique<zmq::socket_t>(*m_context,
                                    zmq::socket_type::pull);
}

Header ReaderZMQ::readHeader(zmq::message_t &header_msg)
{
  Header header;

  header.imagesInBlock = 1;
  if (m_version == 4) {
    header.frameDimensions = SECTOR_DIMENSIONS_VERSION_4;
  } else {
    header.frameDimensions = SECTOR_DIMENSIONS_VERSION_5;
  }
  header.version = m_version;


 // Unpack the message data into a msgpack::object_handle
  msgpack::object_handle oh =
      msgpack::unpack((const char*)header_msg.data(), header_msg.size());

  // Extract the header fields from the unpacked data
  auto map = oh.get().as<std::map<std::string, uint32_t>>();
  header.scanNumber = map["scan_number"];
  header.frameNumber = map["frame_number"];

  // Set the scan dimensions based on the number of STEM positions per row and the number of rows
  header.scanDimensions.first = map["nSTEM_positions_per_row_m1"] ;
  header.scanDimensions.second = map["nSTEM_rows_m1"];

  // Get module here instead of 
  header.sector = map["module"];

  // Calculate the image numbers based on the STEM position and row numbers
  header.imageNumbers.push_back(map["STEM_row_in_scan"] * header.scanDimensions.first +
                                map["STEM_x_position_in_row"]);

  return header;
}

void readSectorDataVersion5(zmq::message_t &data_msg, Block& block, int sector)
{
  auto frameY = sector * SECTOR_DIMENSIONS_VERSION_5.second;
  auto offset = frameY * FRAME_DIMENSIONS.first;

  // Copy the message data into the block buffer
  std::memcpy(block.data.get() + offset, data_msg.data(),
              SECTOR_DIMENSIONS_VERSION_5.first * SECTOR_DIMENSIONS_VERSION_5.second *
                  sizeof(uint16_t));
}

template <typename Functor>
std::future<void> ReaderZMQ::readAll(Functor& func)
{
  m_pool = std::make_unique<ThreadPool>(m_threads);

  // Create worker threads
  for (int i = 0; i < m_threads; i++) {
    m_futures.emplace_back(m_pool->enqueue([this, &func]() {
      
      // TODO: set this true to be reliant on final message from zmq push socket at NERSC
      while (true) {
        zmq::message_t header_msg;
        (*m_pull_socket_data).recv(header_msg, zmq::recv_flags::none);

        // First read the header
        auto header = readHeader(header_msg);
        auto sector = header.sector;

        std::vector<Block> blocks;
        for (unsigned j = 0; j < header.imagesInBlock; j++) {
          auto pos = header.imageNumbers[j];
          auto frameNumber = header.frameNumber;

          std::unique_lock<std::mutex> cacheLock(m_cacheMutex);
          auto& frame = m_frameCache[frameNumber];
          cacheLock.unlock();

          // Do we need to allocate the frame, use a double check lock
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
              std::shared_ptr<uint16_t> data;

              data.reset(
                new uint16_t[frame.block.header.frameDimensions.first *
                             frame.block.header.frameDimensions.second],
                std::default_delete<uint16_t[]>());
              std::fill(data.get(),
                        data.get() +
                          frame.block.header.frameDimensions.first *
                            frame.block.header.frameDimensions.second,
                        0);
              std::atomic_store(&frame.block.data, data);
            }
          }
          zmq::message_t data_msg;
          (*m_pull_socket_data).recv(data_msg, zmq::recv_flags::none);

          readSectorData(data_msg, frame.block, sector);

          // Now now have the complete frame
          if (++frame.sectorCount == 4) {
            cacheLock.lock();
            blocks.emplace_back(frame.block);
            m_frameCache.erase(frameNumber);
            cacheLock.unlock();
          }
        }

        // Finally call the function on any completed frames
        for (auto& b : blocks) {
          func(b);
        }
      }

      // TODO: need logic to count the incomplete blocks.
    }));
  }

  // Return a future that is resolved once the processing is complete
  auto complete = std::async(std::launch::deferred, [this]() {
    for (auto& future : this->m_futures) {
      future.get();
    }
  });

  return complete;
}
} // namespace stempy