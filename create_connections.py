import argparse
import csv
from datetime import datetime
from dateutil.tz import tzutc
from dateutil import parser as date_parser
from google.protobuf import field_mask_pb2
from google.streetview.publish_v1.proto import resources_pb2
from google.streetview.publish_v1.proto import rpcmessages_pb2
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
  flow = OAuth2WebServerFlow(client_id=client_id,
                             client_secret=client_secret,
                             scope='https://www.googleapis.com/auth/streetviewpublish',
                             #,
                             redirect_uri='http://127.0.0.1'
                             )
  storage = Storage('creds.data')
  # Open a web browser to ask the user for credentials.
  credentials = storage.get()
  
  if (credentials.access_token is None) or (credentials.token_expiry < datetime.utcnow()):
    credentials = oauth2_tools.run_flow(flow, storage, flags)
    
  assert credentials.access_token is not None
  return credentials.access_token
  
  
def read_connection_info_from_csv(input_csv):
  upload_info_list = []
  
  with open(input_csv, 'r') as csv_file:
    csv_reader = csv.reader(csv_file)
    for row in csv_reader:
      filename = row[0]
      lat = row[1]
      lng = row[2]
      timestamp = row[3]
      photo_id = row[4]
      upload_url = row[5]
      share_link = row[6]
      prev_image_photo_id = row[7]
      next_image_photo_id = row[8]
      
      my_photo_info = PhotoInfo(filename, lat, lng, timestamp)
      my_photo_info.set_photo_id(photo_id)
      my_photo_info.set_upload_url(upload_url)
      my_photo_info.set_share_link(share_link)
      my_photo_info.set_prev_image_photo_id(prev_image_photo_id)
      my_photo_info.set_next_image_photo_id(next_image_photo_id)
      
      upload_info_list.append(my_photo_info)
  
    csv_file.close()
  return upload_info_list
  
  

def create_connection_updates(upload_info_list):
  """Create a list of photo connection updates."""
  # Set that we're just updating connections
  update_mask = field_mask_pb2.FieldMask()
  update_mask.FromJsonString("connections")
  
  update_photo_req_list = []
  
  for my_photo_info in upload_info_list:
    #Create a new Photo object:
    
    photo = resources_pb2.Photo()
    photo.photo_id.id = my_photo_info.photo_id
    
    
    connections = []
    
    if my_photo_info.next_image_photo_id is not None:
      next_photo_connection = resources_pb2.Connection()
      next_photo_connection.target.id = my_photo_info.next_image_photo_id
      
      connections.append(next_photo_connection)
      
    if my_photo_info.prev_image_photo_id is not None:
      prev_photo_connection = resources_pb2.Connection()
      prev_photo_connection.target.id = my_photo_info.prev_image_photo_id
      
      connections.append(prev_photo_connection)
  
    photo.connections.extend(connections)
    
    # # Now create an UpdatePhotosRequest
    # update_photo_req = rpcmessages_pb2.UpdatePhotoRequest
    # update_photo_req.photo = photo
    # update_photo_req.field_mask = update_mask
    
    update_photo_req_list.append((photo, update_mask))
    
  return update_photo_req_list
    
    
def update_connections(streetview_client, connection_update_list):
  
  for update_photo_item in connection_update_list:
    

    photo = update_photo_item[0]
    update_mask = update_photo_item[1]
    
    print "Attempting update of {0}".format(photo.photo_id.id)
    
    update_photo_response = streetview_client.update_photo(photo, update_mask)
    print "Update Photo Response: " + str(update_photo_response)
    
    time.sleep(5)
  
  print "Update complete!"
  

def main(flags):
  # -----------------------------------
  # Main Code

  input_csv = flags.input_csv
  client_id = flags.client_id
  client_secred = flags.client_secret
  
  upload_info_list = read_connection_info_from_csv(input_csv)
  
  # Convert the upload info list into a set of proto buffers to update photo connections
  connection_update_list = create_connection_updates(upload_info_list)

  
  token = get_access_token(client_id, client_secret, flags)
  print("Token: " + str(token))
  
  credentials = google.oauth2.credentials.Credentials(token)

  # Create a client and request an Upload URL.
  streetview_client = client.StreetViewPublishServiceClient(credentials=credentials)
  
  update_connections(streetview_client, connection_update_list)
  

if __name__ == "__main__":
  parser = argparse.ArgumentParser(description = 'StreetView connection creator',
                                    parents=[oauth2_tools.argparser])
  parser.add_argument('--input_csv', help='A csv file containing photos to link')
  parser.add_argument('--client_id', help='Google API Client Id')
  parser.add_argument('--client_secret', help='Google API Client Secret')
  flags = parser.parse_args()
  main(flags)