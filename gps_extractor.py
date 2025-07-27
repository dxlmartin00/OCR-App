
import re
import time
from typing import List, Dict, Any, Optional, Tuple
import piexif

class GPSExtractor:
    """Enhanced GPS coordinate extractor with improved degree symbol handling and reduced false positives"""
    
    def __init__(self):
        # More comprehensive degree symbol representations
        self.degree_symbols = r'[°º˚o0]|deg(?:rees?)?'
        
        # Enhanced GPS coordinate patterns with better degree handling
        self.gps_patterns = [
            # GPS with explicit labels - highest confidence
            {
                'pattern': rf'(?:GPS|COORDINATES?)[:\s]*\(?([+-]?\d{{1,2}}(?:\.\d{{1,8}})?)(?:{self.degree_symbols}\s*)?,?\s*([+-]?\d{{1,3}}(?:\.\d{{1,8}})?)(?:{self.degree_symbols}\s*)?\)?',
                'priority': 10,
                'type': 'labeled'
            },
            {
                'pattern': rf'(?:LAT|Lat|LATITUDE)[:\s]*([+-]?\d{{1,2}}(?:\.\d{{1,8}})?)(?:{self.degree_symbols}\s*)?([NS])?\s*,?\s*(?:LON|Long|LONGITUDE)[:\s]*([+-]?\d{{1,3}}(?:\.\d{{1,8}})?)(?:{self.degree_symbols}\s*)?([EW])?',
                'priority': 9,
                'type': 'lat_lon'
            },
            
            # Degree-minute-second format with direction indicators (enhanced degree symbol handling)
            {
                'pattern': rf'([NS])\s*(\d{{1,2}})(?:{self.degree_symbols}\s*)(\d{{1,2}})[\'′\s]+(\d{{1,2}}(?:\.\d+)?)[\"″\s]*,?\s*([EW])\s*(\d{{1,3}})(?:{self.degree_symbols}\s*)(\d{{1,2}})[\'′\s]+(\d{{1,2}}(?:\.\d+)?)[\"″\s]*',
                'priority': 9,
                'type': 'dms_dir_first'
            },
            {
                'pattern': rf'(\d{{1,2}})(?:{self.degree_symbols}\s*)(\d{{1,2}})[\'′\s]+(\d{{1,2}}(?:\.\d+)?)[\"″\s]*([NS])\s*,?\s*(\d{{1,3}})(?:{self.degree_symbols}\s*)(\d{{1,2}})[\'′\s]+(\d{{1,2}}(?:\.\d+)?)[\"″\s]*([EW])',
                'priority': 9,
                'type': 'dms_dir_last'
            },
            
            # Degree-decimal minute format (improved symbol handling)
            {
                'pattern': rf'([NS])\s*(\d{{1,2}})(?:{self.degree_symbols}\s*)(\d{{1,2}}\.?\d*)[\'′\s]*,?\s*([EW])\s*(\d{{1,3}})(?:{self.degree_symbols}\s*)(\d{{1,2}}\.?\d*)[\'′\s]*',
                'priority': 8,
                'type': 'dm_dir_first'
            },
            {
                'pattern': rf'(\d{{1,2}})(?:{self.degree_symbols}\s*)(\d{{1,2}}\.?\d*)[\'′\s]*([NS])\s*,?\s*(\d{{1,3}})(?:{self.degree_symbols}\s*)(\d{{1,2}}\.?\d*)[\'′\s]*([EW])',
                'priority': 8,
                'type': 'dm_dir_last'
            },
            
            # Decimal degrees with direction indicators (more flexible)
            {
                'pattern': rf'([NS])\s*([+-]?\d{{1,2}}\.?\d{{0,8}})(?:{self.degree_symbols}\s*)?,?\s*([EW])\s*([+-]?\d{{1,3}}\.?\d{{0,8}})(?:{self.degree_symbols}\s*)?',
                'priority': 7,
                'type': 'decimal_dir_separate'
            },
            {
                'pattern': rf'([+-]?\d{{1,2}}\.?\d{{0,8}})(?:{self.degree_symbols}\s*)?([NS])\s*,?\s*([+-]?\d{{1,3}}\.?\d{{0,8}})(?:{self.degree_symbols}\s*)?([EW])',
                'priority': 7,
                'type': 'decimal_dir_attached'
            },
            
            # Pure decimal degrees with optional degree symbols
            {
                'pattern': rf'([+-]?\d{{1,2}}\.\d{{4,8}})(?:{self.degree_symbols}\s*)?,?\s*([+-]?\d{{1,3}}\.\d{{4,8}})(?:{self.degree_symbols}\s*)?',
                'priority': 5,
                'type': 'pure_decimal'
            },
            
            # New patterns for common variations
            {
                'pattern': rf'([NS])\s*(\d{{1,2}})\s*[°º˚o]\s*(\d{{1,2}})\s*[′\']\s*(\d{{1,2}}\.\d+)\s*[″"]\s*([EW])\s*(\d{{1,3}})\s*[°º˚o]\s*(\d{{1,2}})\s*[′\']\s*(\d{{1,2}}\.\d+)\s*[″"]',
                'priority': 8,
                'type': 'dms_spaced'
            },
            {
                'pattern': rf'(\d{{1,2}})\s*[°º˚o]\s*(\d{{1,2}})\s*[′\']\s*(\d{{1,2}}\.\d+)\s*[″"]\s*([NS])\s*(\d{{1,3}})\s*[°º˚o]\s*(\d{{1,2}})\s*[′\']\s*(\d{{1,2}}\.\d+)\s*[″"]\s*([EW])',
                'priority': 8,
                'type': 'dms_spaced_reversed'
            },
            # Pattern for format like "N 9° 38' 42.861", E 125° 32' 58.411""
            {
                'pattern': rf'([NS])\s+(\d{{1,2}})°\s+(\d{{1,2}})\'\s+(\d{{1,2}}\.\d+)"\s*,\s*([EW])\s+(\d{{1,3}})°\s+(\d{{1,2}})\'\s+(\d{{1,2}}\.\d+)"',
                'priority': 9,
                'type': 'dms_comma_separated'
            }
        ]
        
        # Enhanced exclusion patterns to avoid false positives
        self.exclusion_patterns = [
            r'\d{1,2}:\d{2}:\d{2}',  # Time format (HH:MM:SS)
            r'\d{1,2}:\d{2}\s*(?:AM|PM)',  # 12-hour time
            r'\d{2,4}[-/]\d{1,2}[-/]\d{1,2}',  # Date formats
            r'\d{1,2}/\d{1,2}/\d{2,4}',  # Date format
            r'[\d.]+\s*(?:KB|MB|GB|TB|Kbps|Mbps|Gbps)',  # File sizes/data rates
            r'\$[\d,.]+',  # Currency
            r'[\d.]+\s*(?:MM|CM|M|KM|IN|FT|YD|MI)',  # Measurements
            r'[\d.]+\s*(?:%|PERCENT|PCT)',  # Percentages
            r'[\d.]+\s*(?:V|VOLT|A|AMP|W|WATT|OHM)',  # Electrical measurements
            r'ISO\s*\d+',  # ISO values
            r'F[/\\]\d+',  # F-stop values
            r'\d+\s*(?:MP|MEGAPIXEL|MPX)',  # Camera specs
            r'[\d.]+\s*(?:°C|°F|CELSIUS|FAHRENHEIT|KELVIN)',  # Temperature
            r'SERIAL\s*[:#]?\s*[\w\d-]+',  # Serial numbers
            r'MODEL\s*[:#]?\s*[\w\d-]+',  # Model numbers
            r'VERSION\s*[:#]?\s*[\w\d.]+',  # Version numbers
            r'FOCAL\s*LENGTH\s*[\d.]+',  # Camera focal length
            r'SHUTTER\s*SPEED\s*[\d/]+',  # Camera shutter speed
            r'APERTURE\s*[\d.]+',  # Camera aperture
            r'EXPOSURE\s*[\d.]+',  # Camera exposure
            r'WHITE\s*BALANCE\s*[\w\d]+',  # Camera white balance
            r'RESOLUTION\s*[\d.]+',  # Resolution values
            r'DPI\s*[\d]+',  # DPI values
            r'BITRATE\s*[\d.]+',  # Bitrate values
            r'FRAMERATE\s*[\d.]+',  # Framerate values
            r'BIT\s*DEPTH\s*[\d]+',  # Bit depth
            r'COLOR\s*SPACE\s*[\w]+',  # Color space
            r'CHANNELS\s*[\d]+',  # Channel count
            r'COMPRESSION\s*[\w\d]+',  # Compression
            r'DURATION\s*[\d:.]+',  # Duration/time
            r'FILE\s*SIZE\s*[\d.]+',  # File size
            r'ASPECT\s*RATIO\s*[\d:.]+',  # Aspect ratio
            r'SCAN\s*TYPE\s*[\w]+',  # Scan type
            r'PROFILE\s*[\w\d]+',  # Profile
            r'ENCODER\s*[\w\d]+',  # Encoder
            r'DECODER\s*[\w\d]+',  # Decoder
            r'FORMAT\s*[\w\d]+',  # Format
            r'CODEC\s*[\w\d]+',  # Codec
            r'BIT\s*RATE\s*[\d.]+',  # Bit rate
            r'SAMPLE\s*RATE\s*[\d.]+',  # Sample rate
            r'CHANNEL\s*[\d]+',  # Channel
            r'TRACK\s*[\d]+',  # Track
            r'STREAM\s*[\d]+',  # Stream
            r'LAYER\s*[\d]+',  # Layer
            r'PIXEL\s*FORMAT\s*[\w\d]+',  # Pixel format
            r'COLOR\s*PROFILE\s*[\w\d]+',  # Color profile
            r'GAMMA\s*[\d.]+',  # Gamma
            r'CONTRAST\s*[\d.]+',  # Contrast
            r'BRIGHTNESS\s*[\d.]+',  # Brightness
            r'SATURATION\s*[\d.]+',  # Saturation
            r'HUE\s*[\d.]+',  # Hue
            r'SHARPNESS\s*[\d.]+',  # Sharpness
            r'NOISE\s*REDUCTION\s*[\d.]+',  # Noise reduction
            r'DYNAMIC\s*RANGE\s*[\d.]+',  # Dynamic range
            r'EXPOSURE\s*BIAS\s*[\d.]+',  # Exposure bias
            r'FLASH\s*[\w\d]+',  # Flash
            r'LENS\s*[\w\d]+',  # Lens
            r'FILTER\s*[\w\d]+',  # Filter
            r'PRESET\s*[\w\d]+',  # Preset
            r'PRESSURE\s*[\d.]+',  # Pressure
            r'HUMIDITY\s*[\d.]+',  # Humidity
            r'WIND\s*SPEED\s*[\d.]+',  # Wind speed
            r'ALTITUDE\s*[\d.]+',  # Altitude
            r'DEPTH\s*[\d.]+',  # Depth
            r'WEIGHT\s*[\d.]+',  # Weight
            r'VOLUME\s*[\d.]+',  # Volume
            r'AREA\s*[\d.]+',  # Area
            r'DENSITY\s*[\d.]+',  # Density
            r'VISCOSITY\s*[\d.]+',  # Viscosity
            r'VELOCITY\s*[\d.]+',  # Velocity
            r'ACCELERATION\s*[\d.]+',  # Acceleration
            r'FORCE\s*[\d.]+',  # Force
            r'ENERGY\s*[\d.]+',  # Energy
            r'POWER\s*[\d.]+',  # Power
            r'FREQUENCY\s*[\d.]+',  # Frequency
            r'WAVELENGTH\s*[\d.]+',  # Wavelength
            r'INTENSITY\s*[\d.]+',  # Intensity
            r'LUMINANCE\s*[\d.]+',  # Luminance
            r'ILLUMINANCE\s*[\d.]+',  # Illuminance
            r'RADIANCE\s*[\d.]+',  # Radiance
            r'IRRADIANCE\s*[\d.]+',  # Irradiance
            r'FLUX\s*[\d.]+',  # Flux
            r'LUMINOUS\s*FLUX\s*[\d.]+',  # Luminous flux
            r'LUMINOUS\s*INTENSITY\s*[\d.]+',  # Luminous intensity
            r'LUMINOUS\s*EMITTANCE\s*[\d.]+',  # Luminous emittance
            r'LUMINOUS\s*EXPOSURE\s*[\d.]+',  # Luminous exposure
            r'LUMINOUS\s*ENERGY\s*[\d.]+',  # Luminous energy
            r'LUMINOUS\s*EFFICACY\s*[\d.]+',  # Luminous efficacy
            r'LUMINOUS\s*EFFICIENCY\s*[\d.]+',  # Luminous efficiency
            r'SPECTRAL\s*POWER\s*[\d.]+',  # Spectral power
            r'SPECTRAL\s*ENERGY\s*[\d.]+',  # Spectral energy
            r'SPECTRAL\s*FLUX\s*[\d.]+',  # Spectral flux
            r'SPECTRAL\s*INTENSITY\s*[\d.]+',  # Spectral intensity
            r'SPECTRAL\s*RADIANCE\s*[\d.]+',  # Spectral radiance
            r'SPECTRAL\s*IRRADIANCE\s*[\d.]+',  # Spectral irradiance
            r'SPECTRAL\s*EMITTANCE\s*[\d.]+',  # Spectral emittance
            r'SPECTRAL\s*EXPOSURE\s*[\d.]+',  # Spectral exposure
            r'SPECTRAL\s*LUMINANCE\s*[\d.]+',  # Spectral luminance
            r'SPECTRAL\s*ILLUMINANCE\s*[\d.]+',  # Spectral illuminance
            r'SPECTRAL\s*LUMINOUS\s*FLUX\s*[\d.]+',  # Spectral luminous flux
            r'SPECTRAL\s*LUMINOUS\s*INTENSITY\s*[\d.]+',  # Spectral luminous intensity
            r'SPECTRAL\s*LUMINOUS\s*EMITTANCE\s*[\d.]+',  # Spectral luminous emittance
            r'SPECTRAL\s*LUMINOUS\s*EXPOSURE\s*[\d.]+',  # Spectral luminous exposure
            r'SPECTRAL\s*LUMINOUS\s*ENERGY\s*[\d.]+',  # Spectral luminous energy
            r'SPECTRAL\s*LUMINOUS\s*EFFICACY\s*[\d.]+',  # Spectral luminous efficacy
            r'SPECTRAL\s*LUMINOUS\s*EFFICIENCY\s*[\d.]+',  # Spectral luminous efficiency
            r'PHOTON\s*FLUX\s*[\d.]+',  # Photon flux
            r'PHOTON\s*INTENSITY\s*[\d.]+',  # Photon intensity
            r'PHOTON\s*RADIANCE\s*[\d.]+',  # Photon radiance
            r'PHOTON\s*IRRADIANCE\s*[\d.]+',  # Photon irradiance
            r'PHOTON\s*EMITTANCE\s*[\d.]+',  # Photon emittance
            r'PHOTON\s*EXPOSURE\s*[\d.]+',  # Photon exposure
            r'PHOTON\s*ENERGY\s*[\d.]+',  # Photon energy
            r'PHOTON\s*EFFICACY\s*[\d.]+',  # Photon efficacy
            r'PHOTON\s*EFFICIENCY\s*[\d.]+',  # Photon efficiency
            r'QUANTUM\s*FLUX\s*[\d.]+',  # Quantum flux
            r'QUANTUM\s*INTENSITY\s*[\d.]+',  # Quantum intensity
            r'QUANTUM\s*RADIANCE\s*[\d.]+',  # Quantum radiance
            r'QUANTUM\s*IRRADIANCE\s*[\d.]+',  # Quantum irradiance
            r'QUANTUM\s*EMITTANCE\s*[\d.]+',  # Quantum emittance
            r'QUANTUM\s*EXPOSURE\s*[\d.]+',  # Quantum exposure
            r'QUANTUM\s*ENERGY\s*[\d.]+',  # Quantum energy
            r'QUANTUM\s*EFFICACY\s*[\d.]+',  # Quantum efficacy
            r'QUANTUM\s*EFFICIENCY\s*[\d.]+',  # Quantum efficiency
            r'RADIOMETRIC\s*FLUX\s*[\d.]+',  # Radiometric flux
            r'RADIOMETRIC\s*INTENSITY\s*[\d.]+',  # Radiometric intensity
            r'RADIOMETRIC\s*RADIANCE\s*[\d.]+',  # Radiometric radiance
            r'RADIOMETRIC\s*IRRADIANCE\s*[\d.]+',  # Radiometric irradiance
            r'RADIOMETRIC\s*EMITTANCE\s*[\d.]+',  # Radiometric emittance
            r'RADIOMETRIC\s*EXPOSURE\s*[\d.]+',  # Radiometric exposure
            r'RADIOMETRIC\s*ENERGY\s*[\d.]+',  # Radiometric energy
            r'RADIOMETRIC\s*EFFICACY\s*[\d.]+',  # Radiometric efficacy
            r'RADIOMETRIC\s*EFFICIENCY\s*[\d.]+',  # Radiometric efficiency
            r'PHOTOMETRIC\s*FLUX\s*[\d.]+',  # Photometric flux
            r'PHOTOMETRIC\s*INTENSITY\s*[\d.]+',  # Photometric intensity
            r'PHOTOMETRIC\s*RADIANCE\s*[\d.]+',  # Photometric radiance
            r'PHOTOMETRIC\s*IRRADIANCE\s*[\d.]+',  # Photometric irradiance
            r'PHOTOMETRIC\s*EMITTANCE\s*[\d.]+',  # Photometric emittance
            r'PHOTOMETRIC\s*EXPOSURE\s*[\d.]+',  # Photometric exposure
            r'PHOTOMETRIC\s*ENERGY\s*[\d.]+',  # Photometric energy
            r'PHOTOMETRIC\s*EFFICACY\s*[\d.]+',  # Photometric efficacy
            r'PHOTOMETRIC\s*EFFICIENCY\s*[\d.]+',  # Photometric efficiency
        ]
    
    def is_false_positive(self, text: str) -> bool:
        """Check if text matches exclusion patterns with more context awareness"""
        text_upper = text.upper().strip()
        
        # First check if the text contains GPS-related keywords that might indicate it's valid
        gps_keywords = ['GPS', 'COORD', 'LAT', 'Lat', 'LON', 'Long', 'LATITUDE', 'LONGITUDE', 'MAP', 'LOCATION', 'POSITION']
        if any(keyword in text_upper for keyword in gps_keywords):
            return False
        
        # Then check exclusion patterns
        for pattern in self.exclusion_patterns:
            if re.search(pattern, text_upper, re.IGNORECASE):
                return True
        
        # Additional context checks
        if ':' in text and not any(x in text for x in ['LAT', 'LON', 'GPS']):
            # If it looks like a time or simple label without GPS context
            return True
            
        if len(text.split()) > 5 and not any(x in text for x in ['°', 'º', 'deg', "'", '"']):
            # Long text without any GPS indicators
            return True
            
        return False
    
    def validate_gps_coordinates(self, lat: float, lon: float, source_text: str) -> bool:
        """Enhanced GPS coordinate validation with more context awareness"""
        # Basic range check
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return False
        
        # Check for obvious false positives
        if self.is_false_positive(source_text):
            return False
        
        # Reject coordinates that are too simple (like 1.0, 2.0)
        if abs(lat - round(lat)) == 0 and abs(lon - round(lon)) == 0 and abs(lat) < 10 and abs(lon) < 10:
            return False
        
        # Reject coordinates at exactly 0,0 (Gulf of Guinea - often a default value)
        if lat == 0 and lon == 0:
            return False
        
        # For pure decimal coordinates, require reasonable precision or GPS context
        lat_str = str(abs(lat))
        lon_str = str(abs(lon))
        if '.' in lat_str and '.' in lon_str:
            lat_decimals = len(lat_str.split('.')[1])
            lon_decimals = len(lon_str.split('.')[1])
            
            # If we have GPS context, we can be more lenient with precision
            has_gps_context = any(
                indicator in source_text.upper() 
                for indicator in ['N', 'S', 'E', 'W', 'GPS', 'LAT', 'LON', 'COORD']
            )
            
            if not has_gps_context:
                # Without context, require at least 4 decimal places
                if lat_decimals < 4 or lon_decimals < 4:
                    return False
            else:
                # With context, require at least 2 decimal places
                if lat_decimals < 2 or lon_decimals < 2:
                    return False
        
        # Additional validation based on coordinate values
        # Reject coordinates that are likely in the middle of oceans
        if (-30 < lat < 30) and (-30 < lon < 30):  # Around 0,0
            # Unless we have strong GPS context
            if not any(indicator in source_text.upper() for indicator in ['GPS', 'COORD']):
                return False
                
        # Reject coordinates that are in Antarctica unless explicitly mentioned
        if lat < -60 and 'ANTARCTIC' not in source_text.upper():
            return False
            
        return True
    
    def extract_gps_coordinates(self, text_list: List[str]) -> Optional[Dict[str, Any]]:
        """Extract GPS coordinates from a list of text strings with improved accuracy"""
        # Combine all text and clean it
        combined_text = ' '.join(text_list)
        
        # Enhanced text preprocessing with context preservation
        cleaned_text = re.sub(r'\b(?:EXIF|CAMERA|PHOTO|IMAGE)\b', '', combined_text, flags=re.IGNORECASE)
        
        # Look for GPS context clues that increase confidence
        gps_context_score = self._calculate_gps_context_score(combined_text)
        
        candidates = []
        
        # Try each pattern in priority order
        for pattern_info in sorted(self.gps_patterns, key=lambda x: x['priority'], reverse=True):
            pattern = pattern_info['pattern']
            matches = re.finditer(pattern, combined_text, re.IGNORECASE)
            
            for match in matches:
                result = self._parse_match(match, pattern_info)
                if result and self.validate_gps_coordinates(
                    result['latitude'], 
                    result['longitude'], 
                    result['source_text']
                ):
                    candidates.append({
                        **result,
                        'priority': pattern_info['priority'],
                        'type': pattern_info['type']
                    })
        
        # Return the highest priority valid match
        if candidates:
            best_candidate = max(candidates, key=lambda x: x['priority'])
            # Remove priority and type from final result
            return {
                'latitude': best_candidate['latitude'],
                'longitude': best_candidate['longitude'],
                'source_text': best_candidate['source_text'],
                'extraction_confidence': self._calculate_confidence(best_candidate)
            }
        
        return None
    
    def _calculate_confidence(self, candidate: Dict[str, Any]) -> str:
        """Calculate confidence level based on pattern type and validation"""
        priority = candidate['priority']
        pattern_type = candidate['type']
        
        if priority >= 9:
            return "HIGH"
        elif priority >= 7:
            return "MEDIUM-HIGH"
        elif priority >= 5:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _parse_match(self, match, pattern_info) -> Optional[Dict[str, Any]]:
        """Parse a regex match into GPS coordinates based on pattern type"""
        groups = match.groups()
        pattern_type = pattern_info['type']
        
        try:
            if pattern_type == 'labeled':
                # GPS: lat, lon or similar
                lat, lon = float(groups[0]), float(groups[1])
                
            elif pattern_type == 'lat_lon':
                # LAT: lat N, LON: lon E
                lat = float(groups[0])
                lat_dir = groups[1] if len(groups) > 1 and groups[1] else None
                lon = float(groups[2])
                lon_dir = groups[3] if len(groups) > 3 and groups[3] else None
                
                if lat_dir == 'S' or (lat_dir is None and lat > 0 and 'S' in match.group().upper()):
                    lat = -lat
                if lon_dir == 'W' or (lon_dir is None and lon > 0 and 'W' in match.group().upper()):
                    lon = -lon
                    
            elif pattern_type == 'dms_dir_first':
                # N DD MM SS.ss, E DDD MM SS.ss
                lat = self._dms_to_decimal(float(groups[1]), float(groups[2]), float(groups[3]))
                if groups[0] == 'S': lat = -lat
                lon = self._dms_to_decimal(float(groups[5]), float(groups[6]), float(groups[7]))
                if groups[4] == 'W': lon = -lon
                
            elif pattern_type == 'dms_dir_last':
                # DD MM SS.ss N, DDD MM SS.ss E
                lat = self._dms_to_decimal(float(groups[0]), float(groups[1]), float(groups[2]))
                if groups[3] == 'S': lat = -lat
                lon = self._dms_to_decimal(float(groups[4]), float(groups[5]), float(groups[6]))
                if groups[7] == 'W': lon = -lon
                
            elif pattern_type in ['dm_dir_first', 'dm_dir_last']:
                # Degree-decimal minute formats
                if pattern_type == 'dm_dir_first':
                    lat = self._dm_to_decimal(float(groups[1]), float(groups[2]))
                    if groups[0] == 'S': lat = -lat
                    lon = self._dm_to_decimal(float(groups[4]), float(groups[5]))
                    if groups[3] == 'W': lon = -lon
                else:
                    lat = self._dm_to_decimal(float(groups[0]), float(groups[1]))
                    if groups[2] == 'S': lat = -lat
                    lon = self._dm_to_decimal(float(groups[3]), float(groups[4]))
                    if groups[5] == 'W': lon = -lon
                    
            elif pattern_type in ['decimal_dir_separate', 'decimal_dir_attached']:
                # Decimal degrees with direction
                if pattern_type == 'decimal_dir_separate':
                    lat = float(groups[1])
                    if groups[0] == 'S': lat = -lat
                    lon = float(groups[3])
                    if groups[2] == 'W': lon = -lon
                else:
                    lat = float(groups[0])
                    if groups[1] == 'S': lat = -lat
                    lon = float(groups[2])
                    if groups[3] == 'W': lon = -lon
                    
            elif pattern_type == 'pure_decimal':
                # Pure decimal coordinates - requires extra validation
                lat, lon = float(groups[0]), float(groups[1])
                
            elif pattern_type == 'dms_comma_separated':
                # Format: N 9° 38' 42.861", E 125° 32' 58.411"
                lat = self._dms_to_decimal(float(groups[1]), float(groups[2]), float(groups[3]))
                if groups[0] == 'S': lat = -lat
                lon = self._dms_to_decimal(float(groups[5]), float(groups[6]), float(groups[7]))
                if groups[4] == 'W': lon = -lon
                
            else:
                return None
            
            return {
                'latitude': lat,
                'longitude': lon,
                'source_text': match.group(0).strip()
            }
                
        except (ValueError, IndexError):
            return None
    
    def _dms_to_decimal(self, degrees: float, minutes: float, seconds: float) -> float:
        """Convert degrees, minutes, seconds to decimal degrees"""
        return degrees + minutes/60 + seconds/3600
    
    def _dm_to_decimal(self, degrees: float, minutes: float) -> float:
        """Convert degrees, decimal minutes to decimal degrees"""
        return degrees + minutes/60
    
    def decimal_to_exif_gps(self, lat: float, lon: float) -> Dict[str, Any]:
        """Convert decimal GPS coordinates to EXIF GPS format"""
        
        def decimal_to_dms(decimal_deg: float) -> Tuple[int, int, float]:
            """Convert decimal degrees to degrees, minutes, seconds"""
            decimal_deg = abs(decimal_deg)
            degrees = int(decimal_deg)
            minutes_float = (decimal_deg - degrees) * 60
            minutes = int(minutes_float)
            seconds = (minutes_float - minutes) * 60
            return degrees, minutes, seconds
        
        def float_to_rational(f: float) -> Tuple[int, int]:
            """Convert float to rational number (numerator, denominator)"""
            if f == int(f):
                return int(f), 1
            else:
                # Use high precision for seconds
                precision = 1000000
                return int(f * precision), precision
        
        lat_deg, lat_min, lat_sec = decimal_to_dms(lat)
        lon_deg, lon_min, lon_sec = decimal_to_dms(lon)
        
        gps_data = {
            piexif.GPSIFD.GPSLatitudeRef: 'N' if lat >= 0 else 'S',
            piexif.GPSIFD.GPSLatitude: [
                (lat_deg, 1),
                (lat_min, 1),
                float_to_rational(lat_sec)
            ],
            piexif.GPSIFD.GPSLongitudeRef: 'E' if lon >= 0 else 'W',
            piexif.GPSIFD.GPSLongitude: [
                (lon_deg, 1),
                (lon_min, 1),
                float_to_rational(lon_sec)
            ],
            piexif.GPSIFD.GPSMapDatum: 'WGS-84',
            piexif.GPSIFD.GPSVersionID: (2, 2, 0, 0)
        }
        
        return gps_data
    
    def _calculate_gps_context_score(self, text: str) -> int:
        """Calculate how likely the text contains GPS coordinates based on context"""
        score = 0
        text_upper = text.upper()
        
        # Strong GPS indicators
        strong_indicators = ['GPS', 'COORDINATES', 'LOCATION', 'POSITION', 'WAYPOINT', 'GEOCODED']
        for indicator in strong_indicators:
            if indicator in text_upper:
                score += 3
        
        # Medium GPS indicators
        medium_indicators = ['LAT', 'LON', 'LATITUDE', 'LONGITUDE', 'MAP', 'NAVIGATION']
        for indicator in medium_indicators:
            if indicator in text_upper:
                score += 2
        
        # Weak GPS indicators
        weak_indicators = ['NORTH', 'SOUTH', 'EAST', 'WEST', 'DEGREE', 'MINUTE', 'SECOND']
        for indicator in weak_indicators:
            if indicator in text_upper:
                score += 1
        
        # Direction symbols
        if any(symbol in text for symbol in ['°', '\'', '"', 'N', 'S', 'E', 'W']):
            score += 1
        
        return score