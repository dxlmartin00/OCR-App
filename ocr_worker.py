
import time
from typing import List, Dict, Optional
from PyQt6.QtCore import QThread, pyqtSignal
import easyocr
from gps_extractor import GPSExtractor

class OCRModelCache:
    """Singleton class to cache OCR models"""
    _instance = None
    _models: Dict[str, easyocr.Reader] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(OCRModelCache, cls).__new__(cls)
        return cls._instance
    
    def get_model(self, language: str, use_gpu: bool = False) -> easyocr.Reader:
        """Get cached model or create new one with GPU support"""
        model_key = f"{language}_{'gpu' if use_gpu else 'cpu'}"
        if model_key not in self._models:
            print(f"Loading OCR model for language: {language} ({'GPU' if use_gpu else 'CPU'})")
            try:
                self._models[model_key] = easyocr.Reader([language], gpu=use_gpu)
                print(f"OCR model for {language} loaded and cached")
            except Exception as e:
                print(f"Failed to load GPU model, falling back to CPU: {e}")
                self._models[model_key] = easyocr.Reader([language], gpu=False)
        return self._models[model_key]
    
    def clear_cache(self):
        """Clear all cached models"""
        self._models.clear()

class OCRWorker(QThread):
    """Worker thread for OCR processing"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    model_loading = pyqtSignal(str)  # Signal for model loading status
    
    def __init__(self, image_paths: List[str], language: str = 'en', 
                 use_gpu: bool = False, multi_pass: bool = True, roi_detection: bool = True):
        super().__init__()
        self.image_paths = image_paths
        self.language = language
        self.use_gpu = use_gpu
        self.multi_pass = multi_pass
        self.use_roi_detection = roi_detection
        self.results = []
        self.gps_extractor = GPSExtractor()
        self.model_cache = OCRModelCache()
        
    def run(self):
        try:
            # Get cached OCR model with GPU support
            self.model_loading.emit(f"Loading OCR model for {self.language}...")
            ocr = self.model_cache.get_model(self.language, self.use_gpu)
            self.model_loading.emit("OCR model ready")
            
            total_files = len(self.image_paths)
            
            for i, image_path in enumerate(self.image_paths):
                try:
                    # Multi-pass OCR processing with ROI detection
                    all_results = []
                    
                    if self.use_roi_detection:
                        # Detect potential coordinate regions first
                        roi_results = self._process_coordinate_regions(ocr, image_path)
                        all_results.extend(roi_results)
                    
                    # Pass 1: High confidence threshold (full image)
                    result_high = ocr.readtext(image_path, min_size=10, text_threshold=0.8)
                    all_results.extend(result_high)
                    
                    # Pass 2: Medium confidence for potentially missed text
                    result_medium = ocr.readtext(image_path, min_size=5, text_threshold=0.6)
                    all_results.extend(result_medium)
                    
                    # Pass 3: Low confidence specifically for coordinate patterns
                    result_low = ocr.readtext(image_path, min_size=3, text_threshold=0.4, 
                                            width_ths=0.5, height_ths=0.5)
                    all_results.extend(result_low)
                    
                    # Remove duplicates and merge overlapping detections
                    merged_results = self._merge_detections(all_results)
                    
                    # Format results
                    formatted_result = {
                        'image_path': image_path,
                        'text_data': [],
                        'processed_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'gps_coordinates': None,
                        'all_detected_text': []
                    }
                    
                    extracted_texts = []
                    
                    if merged_results:
                        for detection in merged_results:
                            box = detection[0]  # Coordinates (4 points)
                            text = detection[1]  # Text
                            confidence = detection[2]  # Confidence
                            
                            extracted_texts.append(text)
                            formatted_result['all_detected_text'].append(text)
                            
                            formatted_result['text_data'].append({
                                'text': text,
                                'confidence': confidence,
                                'coordinates': {
                                    'top_left': [int(box[0][0]), int(box[0][1])],
                                    'top_right': [int(box[1][0]), int(box[1][1])],
                                    'bottom_right': [int(box[2][0]), int(box[2][1])],
                                    'bottom_left': [int(box[3][0]), int(box[3][1])]
                                }
                            })
                    
                    # Extract GPS coordinates from all detected text
                    if extracted_texts:
                        gps_coords = self.gps_extractor.extract_gps_coordinates(extracted_texts)
                        if gps_coords:
                            formatted_result['gps_coordinates'] = gps_coords
                    
                    self.results.append(formatted_result)
                    
                    # Update progress
                    progress_percent = int((i + 1) / total_files * 100)
                    self.progress.emit(progress_percent)
                    
                except Exception as e:
                    self.error.emit(f"Error processing {image_path}: {str(e)}")
                    continue
            
            self.finished.emit(self.results)
            
        except Exception as e:
            self.error.emit(f"OCR initialization failed: {str(e)}")
    
    def _merge_detections(self, detections):
        """Merge overlapping text detections and remove duplicates"""
        if not detections:
            return []
        
        # Sort by confidence (highest first)
        sorted_detections = sorted(detections, key=lambda x: x[2], reverse=True)
        merged = []
        
        for detection in sorted_detections:
            box, text, confidence = detection
            
            # Check if this detection overlaps significantly with existing ones
            is_duplicate = False
            for existing in merged:
                if self._boxes_overlap(box, existing[0]) and self._text_similar(text, existing[1]):
                    # Keep the one with higher confidence
                    if confidence > existing[2]:
                        merged.remove(existing)
                        merged.append(detection)
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                merged.append(detection)
        
        return merged
    
    def _boxes_overlap(self, box1, box2, threshold=0.5):
        """Check if two bounding boxes overlap significantly"""
        # Calculate box areas and intersection
        def box_area(box):
            x_coords = [point[0] for point in box]
            y_coords = [point[1] for point in box]
            return (max(x_coords) - min(x_coords)) * (max(y_coords) - min(y_coords))
        
        def boxes_intersect(b1, b2):
            x1_min, x1_max = min(p[0] for p in b1), max(p[0] for p in b1)
            y1_min, y1_max = min(p[1] for p in b1), max(p[1] for p in b1)
            x2_min, x2_max = min(p[0] for p in b2), max(p[0] for p in b2)
            y2_min, y2_max = min(p[1] for p in b2), max(p[1] for p in b2)
            
            x_overlap = max(0, min(x1_max, x2_max) - max(x1_min, x2_min))
            y_overlap = max(0, min(y1_max, y2_max) - max(y1_min, y2_min))
            return x_overlap * y_overlap
        
        intersection = boxes_intersect(box1, box2)
        union = box_area(box1) + box_area(box2) - intersection
        
        return (intersection / union) > threshold if union > 0 else False
    
    def _text_similar(self, text1, text2, threshold=0.8):
        """Check if two text strings are similar"""
        # Simple similarity check
        longer = text1 if len(text1) > len(text2) else text2
        shorter = text2 if len(text1) > len(text2) else text1
        
        if len(longer) == 0:
            return True
        
        # Calculate similarity ratio
        matches = sum(1 for a, b in zip(longer, shorter) if a == b)
        return (matches / len(longer)) > threshold
    
    def _process_coordinate_regions(self, ocr, image_path):
        """Process specific regions likely to contain coordinates"""
        from PIL import Image
        import numpy as np
        
        try:
            # Load image
            img = Image.open(image_path)
            img_array = np.array(img)
            height, width = img_array.shape[:2]
            
            # Define regions of interest (corners and edges where coordinates often appear)
            regions = [
                # Top regions
                (0, 0, width//3, height//4),  # Top-left
                (width*2//3, 0, width, height//4),  # Top-right
                (width//3, 0, width*2//3, height//6),  # Top-center
                
                # Bottom regions  
                (0, height*3//4, width//3, height),  # Bottom-left
                (width*2//3, height*3//4, width, height),  # Bottom-right
                (width//3, height*5//6, width*2//3, height),  # Bottom-center
                
                # Side regions
                (0, height//3, width//6, height*2//3),  # Left-middle
                (width*5//6, height//3, width, height*2//3),  # Right-middle
            ]
            
            roi_results = []
            
            for x1, y1, x2, y2 in regions:
                # Crop region
                region = img.crop((x1, y1, x2, y2))
                
                # Process region with higher sensitivity for coordinates
                region_results = ocr.readtext(np.array(region), 
                                            min_size=2, 
                                            text_threshold=0.3,
                                            width_ths=0.3,
                                            height_ths=0.3)
                
                # Adjust coordinates back to full image
                for detection in region_results:
                    box, text, confidence = detection
                    adjusted_box = [(x + x1, y + y1) for x, y in box]
                    roi_results.append((adjusted_box, text, confidence))
            
            return roi_results
            
        except Exception as e:
            print(f"ROI processing failed: {e}")
            return []
