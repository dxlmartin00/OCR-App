# LIGER - Layer-based Image GPS Extraction and Recognition

[![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![PyQt6](https://img.shields.io/badge/GUI-PyQt6-orange.svg)](https://pypi.org/project/PyQt6/)

**LIGER** is an advanced OCR-based application that extracts GPS coordinates from images containing text and embeds them directly into image metadata. Perfect for geotagging photos, processing screenshots of maps, or extracting location data from any image containing coordinate information.

![LIGER Interface](screenshots/main_interface.png)

## 🌟 Key Features

### 📍 Enhanced GPS Extraction
- **Multiple GPS Format Support**: Recognizes various coordinate formats including:
  - Decimal Degrees: `40.7128, -74.0060`
  - Degrees Minutes Seconds: `40°42'46"N, 74°00'21"W`
  - Degrees Decimal Minutes: `40°42.767'N, 74°00.350'W`
  - Labeled Coordinates: `LAT: 40.7128, LON: -74.0060`
  - GPS Tags: `GPS: (40.7128, -74.0060)`

### 🔍 Advanced OCR Processing
- **EasyOCR Integration**: High-accuracy text recognition
- **Multi-language Support**: English, Chinese, French, German, Korean, Japanese
- **Visual Text Overlay**: See exactly where text was detected
- **False Positive Reduction**: Intelligent filtering to avoid extracting timestamps, file sizes, and other non-GPS data

### 💾 Metadata Embedding
- **EXIF GPS Integration**: Embeds coordinates in standard GPS EXIF fields
- **Cross-platform Compatibility**: GPS data readable by photo viewers, mapping apps, and photo management tools
- **Batch Processing**: Process multiple images simultaneously
- **Original File Preservation**: Option to create copies with GPS data

### 📊 Export Options
- **JSON Export**: Detailed extraction results with confidence scores
- **Image Copies**: Save new versions with embedded GPS metadata
- **Processing Reports**: Complete audit trail of extraction process

## 🚀 Installation

### Prerequisites
- Python 3.7 or higher
- pip package manager

### Dependencies Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/liger-gps-extractor.git
cd liger-gps-extractor

# Install required packages
pip install -r requirements.txt
```

### Requirements.txt
```
PyQt6>=6.0.0
easyocr>=1.6.0
Pillow>=8.0.0
piexif>=1.1.3
```

### Additional Setup
EasyOCR will automatically download language models on first use. Ensure you have a stable internet connection for the initial setup.

## 📖 Usage

### Running the Application
```bash
python main.py
```

### Step-by-Step Guide

1. **Select Images**
   - Click "Select Images" to choose one or more image files
   - Supported formats: PNG, JPG, JPEG, BMP, TIFF, WebP

2. **Configure OCR Settings**
   - Choose the appropriate language for text recognition
   - Default is English (`en`)

3. **Process Images**
   - Click "Extract GPS from Images" to start processing
   - Progress bar shows current processing status
   - View results in real-time as images are processed

4. **Review Results**
   - Select images from the list to view:
     - Original image with text detection overlays
     - Extracted text with confidence scores
     - GPS coordinates (if found)
     - Processing metadata

5. **Export Results**
   - **Embed GPS in Original Files**: Adds GPS metadata to your original images
   - **Save Images with GPS Data**: Creates copies with embedded GPS information
   - **Export to JSON**: Detailed extraction results for analysis

## 🔧 Technical Details

### GPS Coordinate Detection Algorithm

The application uses a sophisticated multi-pattern recognition system with priority-based matching:

1. **Pattern Priority System**: Higher priority patterns (labeled GPS coordinates) are processed first
2. **Validation Layer**: Coordinates are validated for reasonable ranges and precision
3. **False Positive Filtering**: Excludes timestamps, file sizes, measurements, and other non-GPS data
4. **Confidence Scoring**: Each extraction includes a confidence level (HIGH, MEDIUM-HIGH, MEDIUM, LOW)

### Supported GPS Formats

| Format | Example | Priority |
|--------|---------|----------|
| Labeled GPS | `GPS: 40.7128, -74.0060` | HIGH |
| Lat/Lon Labels | `LAT: 40.7128 N, LON: 74.0060 W` | HIGH |
| DMS with Direction | `40°42'46"N, 74°00'21"W` | MEDIUM-HIGH |
| Decimal with Direction | `N40.7128, W74.0060` | MEDIUM |
| Pure Decimal | `40.712800, -74.006000` | LOW |

### EXIF Metadata Structure

GPS coordinates are embedded using standard EXIF GPS tags:
- `GPSLatitude` & `GPSLatitudeRef`
- `GPSLongitude` & `GPSLongitudeRef`
- `GPSMapDatum` (WGS-84)
- `GPSVersionID`

Additional metadata includes:
- Processing timestamp
- Source text that contained GPS coordinates
- OCR confidence scores
- Original filename

## 📁 Project Structure

```
liger-gps-extractor/
├── main.py                 # Main application file
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── LICENSE                # License file
├── screenshots/           # Application screenshots
│   └── main_interface.png
└── examples/              # Example images for testing
    ├── map_screenshot.jpg
    ├── gps_photo.png
    └── coordinates_text.jpg
```

## 🔍 Example Use Cases

### 📱 Map Screenshots
Extract GPS coordinates from:
- Google Maps screenshots
- GPS app displays
- Navigation screenshots
- Survey photos with coordinates

### 📷 Field Photos
Process images containing:
- GPS device displays
- Coordinate annotations
- Survey markers
- Location stamps

### 🗺️ Document Processing
Extract coordinates from:
- Technical reports
- Survey documents
- Research papers
- Field notes

## ⚡ Performance Tips

1. **Image Quality**: Higher resolution images with clear text yield better results
2. **Language Selection**: Choose the correct language model for optimal OCR accuracy
3. **Batch Processing**: Process multiple images together for efficiency
4. **Format Compatibility**: Use JPEG or TIFF for best EXIF metadata support

## 🐛 Troubleshooting

### Common Issues

**OCR Initialization Failed**
- Ensure stable internet connection for EasyOCR model download
- Check available disk space for model storage
- Verify Python version compatibility

**No GPS Coordinates Detected**
- Verify image contains visible coordinate text
- Try different language models
- Check if coordinates match supported formats
- Ensure text is clear and readable

**EXIF Embedding Failed**
- Some image formats don't support EXIF data
- Use "Save Images with GPS Data" for format conversion
- Check file permissions for original images

### Error Reporting
If you encounter issues:
1. Check the console output for detailed error messages
2. Verify all dependencies are installed correctly
3. Test with the provided example images
4. Create an issue on GitHub with error details

## 🤝 Contributing

We welcome contributions! Here's how to get started:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/new-feature`
3. Make your changes and test thoroughly
4. Commit your changes: `git commit -m 'Add new feature'`
5. Push to the branch: `git push origin feature/new-feature`
6. Submit a pull request

### Development Setup
```bash
# Clone your fork
git clone https://github.com/yourusername/liger-gps-extractor.git
cd liger-gps-extractor

# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest tests/
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **EasyOCR**: Excellent OCR library by JaidedAI
- **PyQt6**: Powerful GUI framework
- **piexif**: EXIF data manipulation library
- **Pillow**: Python Imaging Library

## 📧 Support

- **Email**: lummartin@nemsu.edu.ph

## 🔄 Version History

### v1.0.0 (Current)
- Initial release with enhanced GPS extraction
- Multi-format coordinate support
- EXIF metadata embedding
- Batch processing capabilities
- Advanced false positive filtering

---

**Made with ❤️ for the geospatial community**