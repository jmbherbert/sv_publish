class PhotoInfo:
  
  def __init__(self, filename, lat, lng, timestamp):
    self.filename = filename
    self.lat = lat
    self.lng = lng
    self.timestamp = timestamp
    self.photo_id = None
    self.upload_url = None
    self.share_link = None
    self.prev_image_photo_id = None
    self.next_image_photo_id = None
    
    
    
  def set_photo_id(self, photo_id):
    self.photo_id = photo_id
    
  def set_upload_url(self, upload_url):
    self.upload_url = upload_url
    
  def set_share_link(self, share_link):
    self.share_link = share_link
    
  def set_prev_image_photo_id(self, prev_image_photo_id):
    if(prev_image_photo_id != ''):
      self.prev_image_photo_id = prev_image_photo_id
    
  def set_next_image_photo_id(self, next_image_photo_id):
    if(next_image_photo_id != ''):
      self.next_image_photo_id = next_image_photo_id
    
  def get_as_csv_row(self):
    return [self.filename,
            self.lat,
            self.lng,
            self.timestamp,
            self.photo_id,
            self.upload_url,
            self.share_link,
            self.prev_image_photo_id,
            self.next_image_photo_id]
            