from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from datetime import datetime

def get_decimal_from_dms(dms, ref):
    if not dms or not ref:
        return None
    
    degrees = float(dms[0])
    minutes = float(dms[1]) / 60.0
    seconds = float(dms[2]) / 3600.0
    
    if ref in ['S', 'W']:
        return -(degrees + minutes + seconds)
    return degrees + minutes + seconds

def extract_exif_data(image_file):
    """
    Extracts GPS coordinates and Capture Timestamp from Image EXIF.
    Returns: (lat, lon, captured_timestamp) or (None, None, current_time)
    """
    try:
        img = Image.open(image_file)
        exif_data = img._getexif()
        
        if not exif_data:
            return None, None, datetime.now()

        decoded = {}
        for tag, value in exif_data.items():
            decoded[TAGS.get(tag, tag)] = value

        # 1. Extract Timestamp
        captured_time = decoded.get('DateTimeOriginal') or decoded.get('DateTime')
        if captured_time:
            # Format: 'YYYY:MM:DD HH:MM:SS'
            try:
                captured_dt = datetime.strptime(captured_time, '%Y:%m:%d %H:%M:%S')
            except ValueError:
                captured_dt = datetime.now()
        else:
            captured_dt = datetime.now()

        # 2. Extract GPS
        gps_info = decoded.get('GPSInfo')
        lat, lon = None, None
        
        if gps_info:
            gps_data = {}
            for t in gps_info:
                gps_data[GPSTAGS.get(t, t)] = gps_info[t]

            lat = get_decimal_from_dms(gps_data.get('GPSLatitude'), gps_data.get('GPSLatitudeRef'))
            lon = get_decimal_from_dms(gps_data.get('GPSLongitude'), gps_data.get('GPSLongitudeRef'))

        return lat, lon, captured_dt

    except Exception as e:
        print(f"Error extracting EXIF: {e}")
        return None, None, datetime.now()
