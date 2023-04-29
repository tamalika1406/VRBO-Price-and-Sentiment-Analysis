import json
import os
import pandas
import pymongo
import re
from bs4 import BeautifulSoup
from pymongo import MongoClient
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time


cu_path = os.getcwd()
client = pymongo.MongoClient('mongodb://localhost:27017/')


BASE_NAME = "vrbo"
TRANS_FOR_ML = "vrbo_formatted"

# In case that download part shows error in windows PC, then please use 28-34 lines and comment the 37-43 lines.
# The reason because I used the MAC PC.
# The only difference betwenn these two functions is whether or not they save the files as "utf-8" or not.
# If you face the problem of saving the files because of the encoding, please check to use with the one of 28-34 lines' function.


# def save_string(html, filename):
#     try:
#         file = open(filename, "w", encoding='utf-8')
#         file.write(str(html))
#         file.close()
#     except Exception as ex:
#         print('Error: ' + str(ex))


def save_string(html, filename):
    try:
        file = open(filename, "w")
        file.write(str(html))
        file.close()
    except Exception as ex:
        print('Error: ' + str(ex))

def load_string(f):
    try:
        html = open(f, "r", encoding='utf-8').read()
        return html
    except Exception as ex:
        print('Error: ' + str(ex))


# This is the main class function to process all of the function.
# It will scrape the data, and store the data in Mongo DB
class Transform():

  def __init__(self):
    self.vrbo_pages()
    self.vrbo_mangodb()
    self.trans_for_ml()


# The function to download all the hotel page we want to scrap from
  def vrbo_pages(self):
      # city list we want to download from the vrbo page
      cities = ["san-francisco-california", "los-angeles-california", "las-vegas-nevada", "new-york-new-york",
                "chicago-illinois", "boston-massachusetts", "miami-florida", "orlando-(and-vicinity)-florida",
                "honolulu-hawaii", "washington-(and-vicinity)-district-of-columbia"]
      driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
      driver.implicitly_wait(120)
      driver.set_script_timeout(120)
      driver.set_page_load_timeout(120)
      # loop every city in the list, and in each city's vrbo website, we will loop another 10 pages.
      # Most the city has about 4-8 pages, and if the city do not have it, the try except will handle the error and
      # make loop keep running. In each page of the city, there are 50 hotels, I would like to click each hotel page by
      # div tag with class name data-wdio. Since the page will generate a new page, I would like to switch the page
      # handler from 0 to 1, and download the page it just opened, which is the hotel page, than I would like to close the
      # current page, and switch the handler back to main page which is 0.
      for i in cities:
          for j in range(10):
              driver.get(
                  "https://www.vrbo.com/search/keywords:" + i + "-united-states-of-america/page:" + str(j + 1) +
                  "/arrival:2023-04-01/departure:2023-04-02/minNightlyPrice/0?filterByTotalPrice=true&petIncluded=false"
                  "&ssr=true&adultsCount=2&childrenCount=0")
              try:
                  for k in range(50):
                      time.sleep(5)
                      index = "div[data-wdio='Waypoint" + str(k + 1) + "']"
                      vrbo_hotel = driver.find_element(By.CSS_SELECTOR, index)
                      vrbo_hotel.click()
                      time.sleep(5)
                      windows = driver.window_handles
                      driver.switch_to.window(windows[1])
                      page_name = "vrbo_" + i + "_[" + str((50 * j) + (k + 1)) + "].html"
                      save_string(driver.page_source, page_name)
                      driver.close()
                      driver.switch_to.window(windows[0])
                      time.sleep(5)
                      print((50 * j) + (k + 1))
              except Exception as e:
                  print("Error message: ", e)

      driver.quit()


# The function we scrap the page, and store the information into the mangodb
  def vrbo_mangodb(self):
      # same list of the cities
      cities = ["san-francisco-california", "los-angeles-california", "las-vegas-nevada", "new-york-new-york",
                "chicago-illinois", "boston-massachusetts", "miami-florida", "orlando-(and-vicinity)-florida",
                "honolulu-hawaii", "washington-(and-vicinity)-district-of-columbia"]
      vrbo_info = [] # The whole information list that will be push into mangodb
      # loop each city, and each city will loop 400 pages, if some city do not have this many hotel html, try except
      # will help.
      for i in cities:
          for j in range(400):
              try:
                  vrbo_review_full = []
                  type_facs = []
                  page_name = "vrbo_" + i + "_[" + str(j + 1) + "].html"
                  vrbo_page = load_string(page_name)
                  vrbo_soup = BeautifulSoup(vrbo_page, "lxml")
                  # hotel's name
                  vrbo_name = vrbo_soup.select("h1[class='h2 margin-bottom-0x']")[0]
                  # hotel's city
                  vrbo_city = re.sub("-", " ", i)
                  # some basic information about the hotel
                  vrbo_about = vrbo_soup.select("ul[class='four-pack list-unstyled']")
                  vrbo_about_upper = vrbo_soup.select("div[class='four-pack__block-title h3 margin-bottom-0x']")
                  vrbo_type = re.findall("margin-bottom-0x\">(.*?)</div>", str(vrbo_about_upper[0]))[0]
                  vrbo_bedroom = re.findall("margin-bottom-0x\">(.*?)</div>", str(vrbo_about_upper[1]))[0]
                  vrbo_bathroom = re.findall("margin-bottom-0x\">(.*?)</div>", str(vrbo_about_upper[2]))[0]

                  vrbo_about_lower = re.findall("<li class=\"four-pack__detail-item\">(.*?)</li>", str(vrbo_about))
                  vrbo_area = vrbo_bed = vrbo_sleep = vrbo_bath = ""
                  # the basic info, if sq. ft in the list, it will store that element into area, if bad, store to # of bed
                  # if sleep, store to # of sleep, if bath store into # of bath, but if bath contain two element, it will
                  # store both since some hotel may have 3 full and 1 partial bathroom
                  for vrbo_about_lower_info in vrbo_about_lower:
                      if "sq. ft" in vrbo_about_lower_info:
                          vrbo_area = vrbo_about_lower_info
                      elif "bed" in vrbo_about_lower_info:
                          vrbo_bed = vrbo_about_lower_info
                      elif "Sleeps" in vrbo_about_lower_info:
                          vrbo_sleep = vrbo_about_lower_info
                      elif "bath" in vrbo_about_lower_info:
                          if vrbo_bath == "":
                              vrbo_bath = vrbo_about_lower_info
                          else:
                              vrbo_bath = vrbo_bath + " and " + vrbo_about_lower_info
                  # hotel price
                  vrbo_price = vrbo_soup.select("meta[property='og:price:amount']")[0].get('content')
                  # hotel rating score
                  vrbo_rating = vrbo_soup.select("strong[class='reviews-summary__rounded-rating']")
                  # These if-else are checking if some values are Nona or not, if they are, stoer a null to it
                  # if not, keep it with text inside.
                  if vrbo_rating:
                      vrbo_rating = vrbo_rating[0].text
                  else:
                      vrbo_rating = ''
                  # The number of reviews
                  vrbo_review_num = vrbo_soup.select("strong[class='reviews-summary__num-reviews-right-rail text-link']")

                  if vrbo_review_num:
                      vrbo_review_num = vrbo_review_num[0].text
                      vrbo_review_num = re.findall("([0-9]+)", vrbo_review_num)[0]
                  else:
                      vrbo_review_num = ''
                  # The number of additional images that show in the page
                  vrbo_image = vrbo_soup.select("div[class='photo-grid__label']")
                  if vrbo_image:
                      vrbo_image = re.findall(".*?([0-9]+).*", vrbo_image[0].text)
                  else:
                      vrbo_image = ''
                  # The description of the hotel
                  vrbo_text = vrbo_soup.select("div[class='collapsible-content']")
                  if vrbo_text:
                      vrbo_text = vrbo_text[0].text
                  else:
                      vrbo_text = ''
                  # store the amenities to mangodb, it can be found from js code in html file. Use regular expression to
                  # find displayName, and it contains something and is a list, append the first element to our list, and
                  # it check the if it is or not the duplicate thing if not the list, append itself into our list
                  # if nothing in there, append a null to our list.
                  vrbo_amenities_1 = []
                  vrbo_amenities = re.findall("\"displayName\":\"(.*?)\"},\"availability\":\"YES\"", str(vrbo_soup))
                  for vrbo_amenity in vrbo_amenities:
                      if 'displayName' in vrbo_amenity:
                          vrbo_amenity = re.findall("\",\"displayName\":\"(.*)", vrbo_amenity)
                      if not vrbo_amenity:
                          vrbo_amenities_1.append('')
                      elif type(vrbo_amenity) is list:
                          if vrbo_amenity[0] not in vrbo_amenities_1:
                              vrbo_amenities_1.append(vrbo_amenity[0])
                      else:
                          if vrbo_amenity not in vrbo_amenities_1:
                              vrbo_amenities_1.append(vrbo_amenity)
                  # some facilities in the room, such as queen bed, or bath/shower
                  type_fac = vrbo_soup.select("p[class='rooms-and-spaces-room-card__details']")

                  for fac in type_fac:
                      type_facs.append(fac.text)
                  # The review that people wrote to the hotel, the review have header and body, I scrape both of them, and
                  # store them in two list. The two of them have different length, so I compare the two list, and use the
                  # max one to be the length of the loop. Then in the loop, I compare the index and length of the two list
                  # if it is smaller, our list will append the header or body base on which if-else it is, one is control
                  # the header and one for body. if not smaller, I will stop append the element to the list. No matter
                  # which list is shorter, it will append null to our combine list when its element is done to append.
                  vrbo_review = re.findall("\"reviews\":\[(.*?)\"],", str(vrbo_soup))
                  vrbo_review_header = re.findall("\"headline\":\"(.*?)\"", vrbo_review[0])
                  vrbo_review_text = re.findall("[0-9],\"body\":\"(.*?)\"", vrbo_review[0])

                  vrbo_review_len = max(len(vrbo_review_header), len(vrbo_review_text))
                  for vrbo_review_index in range(vrbo_review_len):
                      if vrbo_review_index < len(vrbo_review_header):
                          vrbo_review_1 = vrbo_review_header[vrbo_review_index]
                      else:
                          vrbo_review_1 = ''
                      if vrbo_review_index < len(vrbo_review_text):
                          vrbo_review_1 = vrbo_review_1 + ': ' + vrbo_review_text[vrbo_review_index]
                      else:
                          vrbo_review_1 = vrbo_review_1 + ': ' + ''
                      vrbo_review_full.append(vrbo_review_1)
                  # The near is some famouse place that near to the hotel, I get the information from the page, and
                  # combine the name and distance of the location together
                  vrbo_near = []
                  vrbo_near_name = vrbo_soup.select("span[class='List--item-toi-name']")
                  vrbo_near_mile = vrbo_soup.select("span[class='List--item-toi-distance pull-right']")
                  for index in range(len(vrbo_near_name)):
                      vrbo_near.append(vrbo_near_name[index].text + ': ' + vrbo_near_mile[index].text)
                  # Here is the whole list of dict that we would like to push into mangodb
                  vrbo_info.append({'rank': j + 1, 'name': vrbo_name.text, 'vrbo city': vrbo_city,
                                    'vrbo image': vrbo_image, 'vrbo text': vrbo_text, 'vrbo type': vrbo_type,
                                    'vrbo area': vrbo_area, 'number of bedroom': vrbo_bedroom, 'number of bed': vrbo_bed,
                                    'number of sleepers': vrbo_sleep, 'number of bathroom': vrbo_bathroom,
                                    'number of bath': vrbo_bath, 'type of facilitate': type_facs,
                                    'star rating': vrbo_rating, 'vrbo review': vrbo_review_full,
                                    'number of review': vrbo_review_num, 'vrbo amenities': vrbo_amenities_1,
                                    'vrbo near': vrbo_near, 'vrbo price': vrbo_price})
              except Exception as e:
                  print(e)

      vrbo_db = client[f"{BASE_NAME}"]
      vrbo_collection = vrbo_db[f"{BASE_NAME}"]
      vrbo_collection.insert_many(vrbo_info)


  # This function is to transform the "vrbo" table into "vrbo_formatted" table in Mongo DB 
  # so that we can use these data in ML project as well.
  # The main processing objective is to clean the dataset. 
  def trans_for_ml(self):
    new_data_list = [] # This will be the output that will be put into "vrbo_formatted" table
    # Extract the data from "vrbo" in Mongo DB
    db = client[f'{BASE_NAME}']
    collection = db[f'{BASE_NAME}']
    all_collection = collection.find()
    for each in all_collection:
      # [vrbo image] transformation
      # Create "vrbo_number_images" column
      try:
        num_image = float(each["vrbo image"][0])
        del each["vrbo image"]
        each["vrbo_number_images"] = num_image
      except:
        try:
          del each["vrbo image"]
        except:
          pass
      # [vrbo area] transformation
      # Create "vrbo_area_sq" column
      try:
        area = each["vrbo area"]
        area = float(re.sub("([0-9.]+)(.*)" , r"\1" , area))
        del each["vrbo area"]
        each["vrbo_area_sq"] = area
      except:
        try :
          del each["vrbo area"]
        except :
          pass
      # [number of bed] transformation
      # Create "number_beds" column
      try:
        number_beds = each["number of bed"]
        number_beds = float(re.sub("([0-9.]+)(.*)" , r"\1" , number_beds))
        del each["number of bed"]
        each["number_beds"] = number_beds
      except:
        try:
          del each["number of bed"]
        except:
          pass
      # [number of sleepers] transformation
      # Create "number_sleepers" column
      try:
        number_sleepers = each["number of sleepers"]
        number_sleepers = float(re.sub("(.+?)([0-9.]+)" , r"\2" , number_sleepers))
        del each["number of sleepers"]
        each["number_sleepers"] = number_sleepers
      except:
        try:
          del each["number of sleepers"]
        except:
          pass
      # [number of bathroom] transformation
      try:
        number_bathrooms = each["number of bathroom"]
        number_bathrooms = float(re.sub("([0-9.]+)(.*)" , r"\1" , number_bathrooms))
        del each["number of bathroom"]
        each["number_bathrooms"] = number_bathrooms
      except:
        try:
          del each["number of bathroom"]
        except:
          pass
      # [number of bath] transformation
      # Create "number_baths" column
      try:
        number_baths = each["number of bath"]
        if "full" in number_baths:
          number_baths = float(re.sub("([0-9.]+)(.*)" , r"\1" , number_baths))
        else:
          number_baths = float(re.sub("([0-9.]+)(.*)" , r"\1" , number_baths))
          number_baths = number_baths + 0.5
        del each["number of bath"]
        each["number_baths"] = number_baths
      except:
        try:
          del each["number of bath"]
        except:
          pass
      # [vrbo review] transformation
      # Create "number_reviews" column to count the number of reviews and 
      # "reviews_text" to store the actual review by combining each review with "|||"
      try:
        review_list = []
        number_reviews = len(each["vrbo review"])
        for value in each["vrbo review"]:
          review_list.append(value)
        review_list = "|||".join(review_list)
        del each["vrbo review"]
        each["number_reviews"] = number_reviews
        each["reviews_text"] = review_list
      except:
        try:
          del each["vrbo review"], each["number of review"]
        except:
          pass
      # [vrbo amenities] transformation
      # Create "number_amenities" column to count the number of amenities and 
      # "amenities_text" to store the actual amenities by combining each amenities with "|||"
      try:
        amenities_list = []
        each_amenities = each["vrbo amenities"]
        for value in each_amenities:
          value = value.lower()
          amenities_list.append(value)
        amenities_list = list(set(amenities_list))
        num_ame = len(amenities_list)
        amenities_text = "|||".join(amenities_list)
        del each["vrbo amenities"]
        each["number_amenities"] = num_ame
        each["amenities_text"] = amenities_text
      except:
        try:
          del each["vrbo amenities"]
        except:
          pass
      # [type of facilitate] transformation
      # Create "number_facilitates" column to count the number of facilitates and 
      # "facilitates_text" to store the actual facilitates by combining each facilitates with "|||"
      try:
        facilitate_list = []
        each_facilitate = each["type of facilitate"]
        for value in each_facilitate:
          value = value.lower()
          facilitate_list.append(value)
        facilitate_list = list(set(facilitate_list))
        num_facilitate = len(facilitate_list)
        facilitate_text = "|||".join(facilitate_list)
        del each["type of facilitate"]
        each["number_facilitates"] = num_facilitate
        each["facilitates_text"] = facilitate_text
      except:
        try:
          del each["type of facilitate"]
        except:
          pass
      ## change some of the columns names by adding the _
      each["vrbo_city"] = each["vrbo city"]
      each["vrbo_text"] = each["vrbo text"]
      each["vrbo_type"] = each["vrbo type"]
      each["number_of_bedroom"] = each["number of bedroom"]
      each["star_rating"] = each["star rating"]
      each["vrbo_near"] = each["vrbo near"]
      each["vrbo_price"] = each["vrbo price"]
      del each["vrbo city"], each["vrbo text"], each["vrbo type"], each["number of bedroom"], each["star rating"], each["number of review"], each["vrbo near"], each["vrbo price"]
      new_data_list.append(each)
    # Create "vrbo_formatted" table in MOngo DB
    new_db = client[f'{TRANS_FOR_ML}']
    collection_new = new_db[f'{TRANS_FOR_ML}']
    collection_new.insert_many(new_data_list)


if __name__ == '__main__':
  Transform()
