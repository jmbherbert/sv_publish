import argparse
import csv
from datetime import datetime
from dateutil.tz import tzutc
from dateutil import parser as date_parser
from google.streetview.publish_v1.proto import resources_pb2
from google.streetview.publish_v1 import street_view_publish_service_client as client
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.file import Storage
from oauth2client import tools as oauth2_tools
import google.oauth2.credentials
import os
from photo_info import PhotoInfo
from PIL import Image
from PIL.ExifTags import GPSTAGS
from PIL.ExifTags import TAGS
from pprint import pprint
import requests
import time




def get_access_token(client_id, client_secret, flags):
  """Gets an access token from Google for the APIs"""
  flow = OAuth2WebServerFlow(client_id=client_id,
                             client_secret=client_secret,
                             scope='https://www.googleapis.com/auth/streetviewpublish',
                             #,
                             redirect_uri='http://127.0.0.1'
                             )
  storage = Storage('creds.data')
  # Open a web browser to ask the user for credentials.
  credentials = storage.get()
  
  if (credentials.access_token is None) or (credentials.token_expiry < datetime.now()):
    credentials = oauth2_tools.run_flow(flow, storage, flags)
    
  assert credentials.access_token is not None
  return credentials.access_token
  
  
def get_exif(filename):
  image = Image.open(filename)
  image.verify()
  return image._getexif()
  
def get_labeled_exif(exif):
  labeled_exif = {}
  for (key, val) in exif.items():
    labeled_exif[TAGS.get(key)] = val

  return labeled_exif

def get_geotagging(exif):
  """Gets geotag EXIF info from the labeled EXIF."""
  if not exif:
    raise ValueError("No EXIF metadata found")

  geotagging = {}
  for (idx, tag) in TAGS.items():
    if tag == 'GPSInfo':
      if idx not in exif:
        raise ValueError("No EXIF geotagging found")

      for (key, val) in GPSTAGS.items():
        if key in exif[idx]:
          geotagging[val] = exif[idx][key]

  return geotagging
    
def get_decimal_from_dms(dms, ref):
  """Converts coordinates in deg, min, secs to decimal"""
  degrees = dms[0][0] / dms[0][1]
  minutes = dms[1][0] / dms[1][1] / 60.0
  # Add the 0.0 to force implicit conversion to a double
  seconds = (dms[2][0] / (dms[2][1] + 0.0)) / 3600.0

  if ref in ['S', 'W']:
    degrees = -degrees
    minutes = -minutes
    seconds = -seconds

  return round(degrees + minutes + seconds, 6)

def get_coordinates(geotags):
  """Extracts coordinates from EXIF Geotags, and returns as a (lat, lng) tuple."""
  lat = get_decimal_from_dms(geotags['GPSLatitude'], geotags['GPSLatitudeRef'])

  lon = get_decimal_from_dms(geotags['GPSLongitude'], geotags['GPSLongitudeRef'])

  return (lat,lon)


def get_file_list(directory):
  """Returns the .jpg files in a directory as a list."""
  file_list = []
  for filename in os.listdir(directory):
    if filename.lower().endswith(".jpg"):
      filepath = os.path.join(directory, filename)
      file_list.append(filepath)
  return file_list



def process_file_list(file_list):
  """Takes files from list, and extracts timestamp and coordinates to prepare for upload."""
  upload_info_list = []
  # We need an epoch date to compute seconds from epoch for each image
  epoch_datetime = datetime(1970, 1, 1, 0, 0, 0, tzinfo=tzutc())
  
  file_list.sort()
  for filename in file_list:
    print "Filename: {0}".format(filename)
    
    exif = get_exif(filename)
    labeled_exif = get_labeled_exif(exif)
    
    # Assume collection was done with PST timestamps
    my_datetime = date_parser.parse(labeled_exif['DateTime'] + ' PST')
    utc_datetime = int((my_datetime - epoch_datetime).total_seconds())

    geotags = get_geotagging(exif)
    (lat, lng) = get_coordinates(geotags)
    
    my_photo_info = PhotoInfo(filename, lat, lng, utc_datetime)
    upload_info_list.append(my_photo_info)

  return upload_info_list
  
  
def upload_images(streetview_client, token, upload_info_list):
  """Uploads the images defined in the upload list to StreetView."""
  
  i = 0
  prev_photo_info = None
  
  for my_photo_info in upload_info_list:
    upload_ref = streetview_client.start_upload()
    my_photo_info.set_upload_url = upload_ref.upload_url
    
    # Upload the photo bytes to the Upload URL.
    with open(my_photo_info.filename, "rb") as f:
      print("Uploading file: " + f.name)
      raw_data = f.read()
      headers = {
          "Authorization": "Bearer " + token,
          "Content-Type": "image/jpeg",
          "X-Goog-Upload-Protocol": "raw",
          "X-Goog-Upload-Content-Length": str(len(raw_data)),
      }

      r = requests.post(upload_ref.upload_url, data=raw_data, headers=headers)
      print("Upload response: " + str(r))

    # Upload the metadata of the photo.
    photo = resources_pb2.Photo()
    photo.upload_reference.upload_url = upload_ref.upload_url
    photo.capture_time.seconds = my_photo_info.timestamp
    photo.pose.heading = 0.0
    photo.pose.lat_lng_pair.latitude = my_photo_info.lat
    photo.pose.lat_lng_pair.longitude = my_photo_info.lng
    create_photo_response = streetview_client.create_photo(photo)
    print("Create photoresponse: " + str(create_photo_response))
    
    
    # Update our upload info with the photo_id and the share_url
    my_photo_info.set_photo_id(create_photo_response.photo_id.id)
    my_photo_info.set_share_link(create_photo_response.share_link)
    
    # Update linking
    if prev_photo_info is not None:
      my_photo_info.set_prev_image_photo_id = prev_photo_info.photo_id
      prev_photo_info.set_next_image_photo_id = my_photo_info.photo_id
    
    # Keep a pointer to this photo for linking
    prev_photo_info = my_photo_info
    
  print "Upload of {0} file(s) complete!".format(i)




def write_photo_info_to_csv(upload_info_list):
  """Writes the upload info (with photo_ids) to csv"""
  filename = 'output.csv'
  with open(filename, 'w') as csv_file:
    csv_writer = csv.writer(csv_file)
    
    for my_photo_info in upload_info_list:
      my_csv_info = my_photo_info.get_as_csv_row()
      csv_writer.writerow(my_csv_info)
      
  csv_file.close()


def main(flags):
  
  # -----------------------------------
  # Main Code

  directory = flags.directory
  client_id = flags.client_id
  client_secret = flags.client_secret
  



  file_list = get_file_list(directory)

  upload_info_list = process_file_list(file_list)
  i = 0
  for my_photo_info in upload_info_list:
    print "{0},{1},{2},{3}".format(my_photo_info.lat, 
                           my_photo_info.lng,
                           i,
                           my_photo_info.filename)
    i = i + 1
                                        

  
  token = get_access_token(client_id, client_secret, flags)
  print("Token: " + str(token))
  credentials = google.oauth2.credentials.Credentials(token)

  # Create a client and request an Upload URL.
  streetview_client = client.StreetViewPublishServiceClient(credentials=credentials)

  # Upload images to SV API
  upload_images(streetview_client, token, upload_info_list)

  # Write out metadata to csv for later connection linking
  write_photo_info_to_csv(upload_info_list)
  
  
  

if __name__ == "__main__":
  parser = argparse.ArgumentParser(description = 'StreetView image publisher',
                                    parents=[oauth2_tools.argparser])
  parser.add_argument('--directory', help='A directory of .jpg files to upload')
  parser.add_argument('--client_id', help='Google API Client Id')
  parser.add_argument('--client_secret', help='Google API Client Secret')
  flags = parser.parse_args()
  main(flags)