#include "reader_zmq.h"
#include "reader.h"
#include <atomic>
#include <msgpack.hpp>
#include <zmq.hpp>

namespace stempy {
ReaderZMQ::ReaderZMQ(
  std::vector<std::vector<std::reference_wrapper<zmq::context_t>>>&
    pull_data_contexts,
  zmq::context_t* pull_frame_info_context, uint8_t version, int threads)
  : SectorStreamThreadedReader(version, threads),
    m_pull_frame_info_context(pull_frame_info_context),
    m_pull_data_contexts(pull_data_contexts), m_version(version)
{
  size_t number_of_node_group_push_contexts = pull_data_contexts.size();
  size_t number_of_push_sockets_per_node_group = pull_data_contexts[0].size();

  m_pull_data_addrs.resize(number_of_node_group_push_contexts);
  for (int i = 0; i < number_of_node_group_push_contexts; i++) {
    for (int j = 0; j < number_of_push_sockets_per_node_group; j++) {
      int index = i + j * number_of_node_group_push_contexts;
      m_pull_data_addrs[i].push_back("inproc://" + std::to_string(index));
    }
  }

  setup_sockets();
}

void ReaderZMQ::pull_frame_info()
{
  std::map<unsigned int, unsigned int> scan_num_to_frame_count;
  // Deserialize the received message using msgpack
  zmq::message_t msg;
  // Receive the message from the socket
  (*m_pull_frame_info_socket).recv(msg, zmq::recv_flags::none);
  msgpack::object_handle oh =
    msgpack::unpack(static_cast<const char*>(msg.data()), msg.size());
  oh.get().convert(scan_num_to_frame_count);
  for (auto& frame_count : scan_num_to_frame_count) {
    unsigned int scan_number = frame_count.first;
    std::cout << "setting num msgs: " << m_scan_number_to_num_msgs[scan_number]
              << " -- > "
              << m_scan_number_to_num_msgs[scan_number] + frame_count.second
              << std::endl;
    m_scan_number_to_num_msgs[scan_number] += frame_count.second;
  }
}

void ReaderZMQ::setup_sockets()
{
  std::cout << "Num sockets: " << m_threads << std::endl;
  // Create pull sockets
  m_pull_frame_info_socket = std::make_unique<zmq::socket_t>(
    *m_pull_frame_info_context, zmq::socket_type::pull);
  (*m_pull_frame_info_socket).bind("inproc://frame_info");
}

Header ReaderZMQ::readHeader(zmq::message_t& header_msg)
{
  Header header;
  header.imagesInBlock = 1;
  header.frameDimensions = SECTOR_DIMENSIONS_VERSION_5;
  header.version = m_version;
  // Unpack the message data into a msgpack::object_handle
  msgpack::object_handle oh =
    msgpack::unpack((const char*)header_msg.data(), header_msg.size());

  // Extract the header fields from the unpacked data
  auto map = oh.get().as<std::map<std::string, msgpack::object>>();
  header.scanNumber = map["scan_number"].as<uint32_t>();

  header.frameNumber = map["frame_number"].as<uint32_t>();

  header.scanDimensions.first =
    map["nSTEM_positions_per_row_m1"].as<uint16_t>();

  header.scanDimensions.second = map["nSTEM_rows_m1"].as<uint16_t>();

  auto scanXposition = map["STEM_x_position_in_row"].as<uint16_t>();
  auto scanYposition = map["STEM_row_in_scan"].as<uint16_t>();

  header.sector = map["module"].as<uint32_t>();

  header.imageNumbers.push_back(scanYposition * header.scanDimensions.first +
                                scanXposition);

  return header;
}

// TODO: can make this agnostic to previous version
void ReaderZMQ::readSectorDataVersion5(zmq::message_t& data_msg, Block& block,
                                       int sector)
{
  auto frameY = sector * SECTOR_DIMENSIONS_VERSION_5.second;
  auto offset = frameY * FRAME_DIMENSIONS.first;

  // Copy the message data into the block buffer
  std::memcpy(block.data.get() + offset, data_msg.data(),
              SECTOR_DIMENSIONS_VERSION_5.first *
                SECTOR_DIMENSIONS_VERSION_5.second * sizeof(uint16_t));
}

} // namespace stempy