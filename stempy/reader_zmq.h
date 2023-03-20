#ifndef STEMPY_READER_ZMQ_H
#define STEMPY_READER_ZMQ_H

#include "reader.h"
#include <msgpack.hpp>
#include <zmq.hpp>

namespace stempy {

class ReaderZMQ : public SectorStreamThreadedReader
{
public:
  ReaderZMQ(zmq::context_t* context, uint8_t version = 5, int threads = 0);

  template <typename Functor>
  std::future<void> readAll(Functor& f) override;
  Header readHeader(zmq::message_t &header_msg);
  void setup_sockets();
  void readSectorDataVersion5(zmq::message_t &data_msg, Block& block, int sector);

private:
  zmq::context_t* m_context;
  uint8_t m_version;
  std::unique_ptr<zmq::socket_t> m_pull_socket_data;

};
} // namespace stempy
#endif /* STEMPY_READER_ZMQ_H */
