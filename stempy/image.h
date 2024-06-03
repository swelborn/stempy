#ifndef stempyimages_h
#define stempyimages_h

#include "mask.h"

#include <memory>
#include <vector>

namespace stempy {

  template <typename T>
  struct Image
  {
    Dimensions2D dimensions = { 0, 0 };
    std::shared_ptr<T> data;

    Image() = default;
    Image(Dimensions2D dimensions);
    Image(Image&& i) noexcept = default;
    Image& operator=(Image&& i) noexcept = default;
  };

  template <typename T>
  Image<T>::Image(Dimensions2D dims)
    : dimensions(dims),
      data(new T[dims.first * dims.second], std::default_delete<T[]>())
  {
    std::fill(this->data.get(), this->data.get() + dims.first * dims.second, 0);
  }

  struct STEMValues {
    uint64_t data = 0;
    uint32_t imageNumber = -1;
  };

  template <typename T>
  struct RadialSum {
    Dimensions2D dimensions = { 0, 0 };
    uint32_t radii = 0;
    std::shared_ptr<T> data;

    RadialSum() = default;
    RadialSum(Dimensions2D dimensions, uint32_t radii);
    RadialSum(RadialSum&& i) noexcept = default;
    RadialSum& operator=(RadialSum&& i) noexcept = default;
  };

  using STEMImage = Image<uint64_t>;

  // Create STEM Images from raw data
  template <typename InputIt>
  std::vector<STEMImage> createSTEMImages(
    InputIt first, InputIt last, const std::vector<int>& innerRadii,
    const std::vector<int>& outerRadii, Dimensions2D scanDimensions = { 0, 0 },
    Coordinates2D center = { -1, -1 });

  // Create STEM Images from sparse data
  template <typename T>
  void calculateSTEMValuesSparse(const std::vector<std::vector<T>>& sparseData,
                                 uint16_t* mask, STEMImage& image)
  {
    for (unsigned i = 0; i < sparseData.size(); ++i) {
      for (unsigned j = 0; j < sparseData[i].size(); ++j) {
        uint64_t values = 0;
        for (unsigned k = 0; k < sparseData[i][j].size(); ++k) {
          // This access is a little ugly, but its needed to be compatible with
          // both vector<uint32_t> and py:array_t<uint32_t>
          auto pos = sparseData[i][j].data()[k];
          values += mask[pos];
        }
        image.data.get()[i] += values;
      }
    }
  }

  template <typename T>
  std::vector<STEMImage> createSTEMImages(
    const std::vector<std::vector<T>>& sparseData,
    const std::vector<int>& innerRadii, const std::vector<int>& outerRadii,
    Dimensions2D scanDimensions = { 0, 0 },
    Dimensions2D frameDimensions = { 0, 0 }, Coordinates2D center = { -1, -1 })
  {
    if (innerRadii.empty() || outerRadii.empty()) {
      std::ostringstream msg;
      msg << "innerRadii or outerRadii are empty!";
      throw std::invalid_argument(msg.str());
    }

    if (innerRadii.size() != outerRadii.size()) {
      std::ostringstream msg;
      msg << "innerRadii and outerRadii are not the same size!";
      throw std::invalid_argument(msg.str());
    }

    std::vector<STEMImage> images;
    std::vector<uint16_t*> masks;
    for (size_t i = 0; i < innerRadii.size(); ++i) {
      images.push_back(STEMImage(scanDimensions));
      masks.push_back(createAnnularMask(frameDimensions, innerRadii[i],
                                        outerRadii[i], center));
    }

    for (size_t i = 0; i < masks.size(); ++i)
      calculateSTEMValuesSparse(sparseData, masks[i], images[i]);

    for (auto* p : masks)
      delete[] p;

    return images;
  }

  // Create STEM Images from electron counted sparse data
  struct ElectronCountedData;
  std::vector<STEMImage> createSTEMImages(
    const ElectronCountedData& sparseData, const std::vector<int>& innerRadii,
    const std::vector<int>& outerRadii, Coordinates2D center = { -1, -1 });

  STEMValues calculateSTEMValues(const uint16_t data[], uint64_t offset,
                                 uint32_t numberOfPixels, uint16_t mask[],
                                 uint32_t imageNumber = -1);

  template <typename InputIt>
  Image<double> calculateAverage(InputIt first, InputIt last);

  template <typename InputIt>
  RadialSum<uint64_t> radialSum(InputIt first, InputIt last,
                                Dimensions2D scanDimensions = { 0, 0 },
                                Coordinates2D center = { -1, -1 });

  // bins for histogram
  std::vector<double> getContainer(const STEMImage& inImage, const int numBins);
  // histogram and bins for the input STEM image
  std::vector<int> createSTEMHistogram(const STEMImage& inImage,
                                       const int numBins,
                                       const std::vector<double> bins);

  template <typename InputIt>
  Image<double> maximumDiffractionPattern(InputIt first, InputIt last,
                                          const Image<float>& darkreference);

  template <typename InputIt>
  Image<double> maximumDiffractionPattern(InputIt first, InputIt last);

} // namespace stempy

#endif
