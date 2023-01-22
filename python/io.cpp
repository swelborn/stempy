#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <vector>

#include <python/pyreader.h>
#include <stempy/reader.h>

#include "config.h"

namespace py = pybind11;

using namespace stempy;

PYBIND11_MODULE(_io, m)
{
  py::class_<Header>(m, "_header")
    .def_readwrite("images_in_block", &Header::imagesInBlock)
    .def_readwrite("frame_dimensions", &Header::frameDimensions)
    .def_readwrite("version", &Header::version)
    .def_readwrite("timestamp", &Header::timestamp)
    .def_readwrite("image_numbers", &Header::imageNumbers)
    .def_readwrite("scan_dimensions", &Header::scanDimensions)

    .def(py::pickle(
      [](Header& h) { // __getstate__
        /* Return a tuple that fully encodes the state of the object */
        // return py::make_tuple(h.getImagesInBlock(), h.getframeDimensions(),
        //                       h.getVersion(), h.getTimestamp(),
        //                       h.getImageNumbers(), h.getScanDimensions());
        return py::make_tuple(h.imagesInBlock, h.frameDimensions, h.version,
                              h.timestamp, h.imageNumbers, h.scanDimensions);
      },
      [](py::tuple t) { // __setstate__
        if (t.size() != 6)
          throw std::runtime_error("Invalid state!");

        /* Create a new C++ instance */
        Header h;
        h.imagesInBlock = t[0].cast<std::uint32_t>();
        h.frameDimensions = t[1].cast<std::pair<uint32_t, uint32_t>>();
        h.version = t[2].cast<std::uint32_t>();
        h.timestamp = t[3].cast<std::uint32_t>();
        h.imageNumbers = t[4].cast<std::vector<uint32_t>>();
        h.scanDimensions = t[5].cast<std::pair<uint32_t, uint32_t>>();

        return h;
      }));

  py::class_<Block>(m, "_block", py::buffer_protocol())
    .def_readonly("header", &Block::header)
    .def_buffer([](Block& b) {
      return py::buffer_info(
        // const_cast is needed because the buffer_info constructor
        // requires a non-const pointer. pybind11 also internally uses
        // const_cast to achieve the same purpose.
        const_cast<uint16_t*>(b.data.get()),       /* Pointer to buffer */
        sizeof(uint16_t),                          /* Size of one scalar */
        py::format_descriptor<uint16_t>::format(), /* Python struct-style format
                                                      descriptor */
        3,                                         /* Number of dimensions */
        { b.header.imagesInBlock, b.header.frameDimensions.second,
          b.header.frameDimensions.first }, /* Buffer dimensions */
        { sizeof(uint16_t) * b.header.frameDimensions.second *
            b.header.frameDimensions.first,
          sizeof(uint16_t) * b.header.frameDimensions.second, sizeof(uint16_t) }
        /* Strides (in bytes) for each index */
      );
    });
  // .def(py::pickle(
  //   [](const Block& b) { // __getstate__
  //     /* Return a tuple that fully encodes the state of the object */
  //     return py::make_tuple(b.data.get());
  //   },
  //   [](py::tuple t) { // __setstate__
  //     if (t.size() != 2)
  //       throw std::runtime_error("Invalid state!");

  //     /* Create a new C++ instance */

  //     Block b;
  //     b.data.reset(t[0].cast<uint16_t*>());

  //     return b;
  //   }));

  py::class_<PyBlock>(m, "_pyblock", py::buffer_protocol())
    .def_readonly("header", &PyBlock::header)
    .def_buffer([](PyBlock& b) {
      return py::buffer_info(
        // const_cast is needed because the buffer_info constructor
        // requires a non-const pointer. pybind11 also internally uses
        // const_cast to achieve the same purpose.
        const_cast<uint16_t*>(b.data.get()),       /* Pointer to buffer */
        sizeof(uint16_t),                          /* Size of one scalar */
        py::format_descriptor<uint16_t>::format(), /* Python struct-style format
                                                      descriptor */
        3,                                         /* Number of dimensions */
        { b.header.imagesInBlock, b.header.frameDimensions.second,
          b.header.frameDimensions.first }, /* Buffer dimensions */
        { sizeof(uint16_t) * b.header.frameDimensions.second *
            b.header.frameDimensions.first,
          sizeof(uint16_t) * b.header.frameDimensions.second, sizeof(uint16_t) }
        /* Strides (in bytes) for each index */
      );
    });

  py::class_<StreamReader::iterator>(m, "_reader_iterator")
    .def(py::init<StreamReader*>());

  py::class_<StreamReader>(m, "_reader")
    .def(py::init<const std::string&, uint8_t>())
    .def(py::init<const std::vector<std::string>&, uint8_t>())
    .def("read", (Block(StreamReader::*)()) & StreamReader::read)
    .def("reset", &StreamReader::reset)
    .def("begin",
         (StreamReader::iterator(StreamReader::*)()) & StreamReader::begin)
    .def("end",
         (StreamReader::iterator(StreamReader::*)()) & StreamReader::end);

  py::class_<PyReader::iterator>(m, "_pyreader_iterator")
    .def(py::init<PyReader*>());

  py::class_<PyReader>(m, "_pyreader")
    .def(py::init<py::object, std::vector<uint32_t>&, Dimensions2D, uint32_t,
                  uint32_t>())
    .def("read", (PyBlock(PyReader::*)()) & PyReader::read)
    .def("reset", &PyReader::reset)
    .def("begin", (PyReader::iterator(PyReader::*)()) & PyReader::begin)
    .def("end", (PyReader::iterator(PyReader::*)()) & PyReader::end);

  py::class_<SectorStreamReader::iterator>(m, "_sector_reader_iterator")
    .def(py::init<SectorStreamReader*>());

  py::class_<SectorStreamReader> sectorReader(m, "_sector_reader");

  sectorReader.def(py::init<const std::string&, uint8_t>());
  sectorReader.def(py::init<const std::vector<std::string>&, uint8_t>());
  sectorReader.def("read",
                   (Block(SectorStreamReader::*)()) & SectorStreamReader::read);
  sectorReader.def("reset", &SectorStreamReader::reset);
  sectorReader.def("begin",
                   (SectorStreamReader::iterator(SectorStreamReader::*)()) &
                     SectorStreamReader::begin);
  sectorReader.def("end",
                   (SectorStreamReader::iterator(SectorStreamReader::*)()) &
                     SectorStreamReader::end);
  sectorReader.def("data_captured", &SectorStreamReader::dataCaptured);

#ifdef ENABLE_HDF5
  py::enum_<SectorStreamReader::H5Format>(sectorReader, "H5Format")
    .value("Frame", SectorStreamReader::H5Format::Frame)
    .value("DataCube", SectorStreamReader::H5Format::DataCube)
    .export_values();

  sectorReader.def("to_hdf5", &SectorStreamReader::toHdf5, "Write data to HDF5",
                   py::arg("path"),
                   py::arg("format") = SectorStreamReader::H5Format::Frame);
#endif // ENABLE_HDF5

  py::class_<SectorStreamThreadedReader>(m, "_threaded_reader")
    .def(py::init<const std::string&, uint8_t, int>(), py::arg("path"),
         py::arg("version") = 5, py::arg("threads") = 0)
    .def(py::init<const std::vector<std::string>&, uint8_t, int>(),
         py::arg("files"), py::arg("version") = 5, py::arg("threads") = 0);
  py::class_<SectorStreamMultiPassThreadedReader>(m,
                                                  "_threaded_multi_pass_reader")
    .def(py::init<const std::string&, int>(), py::arg("path"),
         py::arg("threads") = 0)
    .def(py::init<const std::vector<std::string>&, int>(), py::arg("files"),
         py::arg("threads") = 0)
    .def("create_scan_map", &SectorStreamMultiPassThreadedReader::createScanMap)
    .def("get_block_from_image_number",
         &SectorStreamMultiPassThreadedReader::getBlockFromMap);
}
