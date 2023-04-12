#include "reader_zmq.h"
#include "reader.h"
#include <atomic>
#include <msgpack.hpp>
#include <zmq.hpp>

namespace stempy {

// Constructor for ReaderZMQ class
ReaderZMQ::ReaderZMQ(
  std::vector<std::vector<std::shared_ptr<zmq::context_t>>>& pull_data_contexts,
  zmq::context_t* pull_frame_info_context, uint8_t version, int threads)
  : SectorStreamThreadedReader(version, threads),
    m_pull_frame_info_context(pull_frame_info_context),
    m_pull_data_contexts(pull_data_contexts), m_version(version)
{
  setup_pull_data_addrs();
  setup_sockets();
}

// Sets up the addresses for the pull data sockets
void ReaderZMQ::setup_pull_data_addrs()
{
  // Resize the address vector to hold 4 groups of addresses
  m_pull_data_addrs.resize(4);
  // Loop through the node groups
  for (int node_group_number = 0; node_group_number < 4; node_group_number++) {
    // Loop through the sockets within a node group
    for (int socket_idx_in_node_group = 0; socket_idx_in_node_group < 4;
         socket_idx_in_node_group++) {
      // Calculate the index for the address
      int index = node_group_number + socket_idx_in_node_group * 4;
      // Generate and store the address for the current socket
      m_pull_data_addrs[node_group_number].push_back("inproc://" +
                                                     std::to_string(index));
    }
  }
}

// Pulls frame information from the ZMQ socket
void ReaderZMQ::pull_frame_info()
{
  std::map<unsigned int, unsigned int> scan_num_to_frame_count;
  // Deserialize the received message using msgpack
  zmq::message_t msg;
  // Receive the message from the socket
  (*m_pull_frame_info_socket).recv(msg, zmq::recv_flags::none);
  msgpack::object_handle oh =
    msgpack::unpack(static_cast<const char*>(msg.data()), msg.size());
  // Convert the deserialized message into a map of scan numbers to frame counts
  oh.get().convert(scan_num_to_frame_count);
  // Update the internal map with the received frame counts
  for (auto& frame_count : scan_num_to_frame_count) {
    unsigned int scan_number = frame_count.first;
    m_scan_number_to_num_msgs[scan_number] += frame_count.second;
  }
}

// Set up the sockets for ZMQ communication
void ReaderZMQ::setup_sockets()
{
  // Create a frame info pull socket
  m_pull_frame_info_socket = std::make_unique<zmq::socket_t>(
    *m_pull_frame_info_context, zmq::socket_type::pull);
  // Bind the frame info pull socket to the frame info address
  (*m_pull_frame_info_socket).bind("inproc://frame_info");

  // Resize the pull data sockets vector
  m_pull_data_sockets.resize(m_threads);
  // Loop through all the threads
  for (unsigned int i = 0; i < m_threads; i++) {
    // Calculate the group and socket indices
    int group_index = i % m_pull_data_contexts.size();
    int socket_index = (i / m_pull_data_contexts.size()) %
                       m_pull_data_contexts[group_index].size();
    // Create a new pull data socket and connect it to the appropriate address
    m_pull_data_sockets.push_back(std::make_unique<zmq::socket_t>(
      (*m_pull_data_contexts[group_index][socket_index]),
      zmq::socket_type::pull));
    (*m_pull_data_sockets[i])
      .connect(m_pull_data_addrs[group_index][socket_index]);
  }
}

// Read the header information from the ZMQ message and return a Header object
Header ReaderZMQ::readHeader(zmq::message_t& header_msg)
{
  // Unpack the message data into a msgpack::object_handle
  msgpack::object_handle oh = msgpack::unpack(
    static_cast<const char*>(header_msg.data()), header_msg.size());
  msgpack::object deserialized_obj = oh.get();

  // Convert the deserialized object into a HeaderZMQ object
  HeaderZMQ received_header_zmq;
  deserialized_obj.convert(received_header_zmq);

  // Initialize block header, see constructor of Header
  Header header(received_header_zmq);

  // Return the block header
  return header;
}

// Read sector data (version 5) from the ZMQ message and store it in the
// provided block
void ReaderZMQ::readSectorDataVersion5(zmq::message_t& data_msg, Block& block,
                                       int sector)
{
  // Calculate the offset in the frame based on the sector number
  auto frameY = sector * SECTOR_DIMENSIONS_VERSION_5.second;
  auto offset = frameY * FRAME_DIMENSIONS.first;

  // Copy the sector data from the received message to the block data
  std::memcpy(block.data.get() + offset, data_msg.data(),
              SECTOR_DIMENSIONS_VERSION_5.first *
                SECTOR_DIMENSIONS_VERSION_5.second * sizeof(uint16_t));
}

} // namespace stempy