# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# [START gae_python38_render_template]
# [START gae_python3_render_template]
import datetime
import os
from flask import Flask, render_template, request, redirect, session
from google.cloud import datastore, storage
from google.auth.transport import requests
import google.oauth2.id_token
import local_constants

app = Flask(__name__)
app.secret_key = "mysecretkey" #secret key for flask session

datastore_client = datastore.Client()
firebase_request_adapter = requests.Request()


# The root route/landing page
# template variables
# user_data: firebase user auth object
# error_message: session error message
# success_message: session success message
# user_info: basic user info
# gallery_list: array of galleries of the loggedin user
# storage_size: the calculated size of the uploaded images
@app.route('/')
def root():
    id_token = request.cookies.get("token")
    error_message = None # session error messsage to display
    success_message = None # session success messsage to display
    claims = None # firebase auth object
    user_info = None # basic user info
    gallery_list = [] # list of all the galleries of the current user

    session["gallery"] = None # used to determine if the requesting user is the owner

    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
            
            user_info = retrieveUserInfo(claims)

            if user_info == None:
                createUserInfo(claims)
                user_info = retrieveUserInfo(claims)

            blob_list = blobList(claims['user_id'])
            bucket = getBucket()
            storage_size = getGallerySize(claims)

            for i in blob_list:
                blob_path = i.name
                blob = bucket.get_blob(blob_path)

                # check if file or directory belongs to user
                # valide file extension to be JPEG or PNG
                split_tup = i.name.split('/')
                directory_prefix = split_tup[0]

                print(split_tup[len(split_tup)-1])

                if directory_prefix == claims['user_id']:
                    if len(split_tup) > 2 and i.name[len(i.name) - 1] == '/':
                        i.gallery_name = split_tup[len(split_tup)-2]
                        gallery_list.append(i)

                print("===================")

            if "error_message" in session:
                if session['error_message'] != None:
                    error_message = session['error_message']
                    session['error_message'] = None

            if "success_message" in session:
                if session['success_message'] != None:
                    success_message = session['success_message']
                    session['success_message'] = None
                
        except ValueError as exc:
            error_message = str(exc)


    return render_template(
        'index.html',
        user_data=claims, 
        error_message=error_message, 
        success_message=success_message, 
        user_info=user_info,
        gallery_list=gallery_list,
        storage_size=storage_size
    )


# POST route to add a gallery
# request form
# gallery_name: user provided gallery name
@app.route('/add_gallery', methods=['POST'])
def addGalleryHandler():
    id_token = request.cookies.get("token")
    claims = None
    
    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
            gallery_name = request.form['gallery_name']

            if gallery_name == '':
                session['error_message'] = "Invalid gallery name"
                return redirect('/')
            
            addGallery(gallery_name, claims)
            session['success_message'] = "gallery created"
        
        except ValueError as exc:
            session['error_message'] = str(exc)
    return redirect('/')

# GET route to see the images in a gallery
# expected args
# gallery_name: name of the gallery that user clicks
@app.route('/gallery')
def gotoGallery():
    id_token = request.cookies.get("token")
    error_message = None
    success_message = None
    claims = None
    user_info = None
    file_list = []

    if id_token:
        try:

            gallery_name = request.args.get('gallery_name');
            session["gallery"] = gallery_name
            
            if len(gallery_name) == 0:
                session['error_message'] = "Invalid gallery url"
                return('/')

            claims = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
            
            user_info = retrieveUserInfo(claims)

            if user_info == None:
                createUserInfo(claims)
                user_info = retrieveUserInfo(claims)

            blob_list = blobList(claims['user_id']+"/"+gallery_name)
            bucket = getBucket()

            storage_size = getGallerySize(claims)

            for i in blob_list:
                blob_path = i.name
                blob = bucket.blob(blob_path)
                print(blob)

                # check if file or directory belongs to user
                # valide file extension to be JPEG or PNG
                split_tup = i.name.split('/')
                print("SPLIT:", split_tup)

                file_name = split_tup[len(split_tup)-1]
                print("FILENAME:", file_name, i.name[len(i.name) - 1])
                print("i.name", i.name)
                print("=============================")

                if len(file_name) > 0 and i.name[len(i.name) - 1] != '/':
                    url = blob.generate_signed_url(datetime.timedelta(seconds=3600), method='GET') #for 1 hour
                    file_list.append({
                        "url": url,
                        "file_name": file_name,
                        "path": i.name
                    })

                if "error_message" in session:
                    if session['error_message'] != None:
                        error_message = session['error_message']
                        session['error_message'] = None

                if "success_message" in session:
                    if session['success_message'] != None:
                        success_message = session['success_message']
                        session['success_message'] = None

        except ValueError as exc:
            error_message = str(exc)

    return render_template(
        'gallery.html',
        user_data=claims, 
        error_message=error_message, 
        success_message=success_message, 
        user_info=user_info, 
        file_list=file_list,
        gallery_name=gallery_name,
        storage_size=storage_size
        
    )

# Delete a gallery
# request form
# gallery_name: name of the gallery that the users whishes to delete
@app.route('/delete_gallery', methods=['POST'])
def deleteGalleryHandler():
    id_token = request.cookies.get("token")
    claims = None
    
    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
            gallery_name = request.form['gallery_name']

            if gallery_name == '':
                session['error_message'] = "Invalid gallery name"
                return redirect('/')
            
            if gallery_name[len(gallery_name) - 1] != '/':
                gallery_name = gallery_name+"/"

            if claims['user_id'] not in gallery_name:
                session['error_message'] = "Invalid operation"
                return redirect('/')

            deleteGallery(gallery_name)
            session['success_message'] = "Gallery deleted"
        
        except ValueError as exc:
            session['error_message'] = str(exc)
    return redirect('/')

# POST route to upload an image
# request form
# file_name: the uploaded image file
# gallery_name: name of the gallery where the user wants to upload the image
@app.route('/upload_file', methods=['post'])
def uploadFileHandler():
    id_token = request.cookies.get("token")
    claims = None
    MAX_STORAGE_SIZE=50
    
    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
            file = request.files['file_name']
            gallery_name = request.form['gallery_name']


            blob = request.files['file_name'].read()
            request.files['file_name'].seek(0)
            size = len(blob)/1000/1000
            gallery_size = getGallerySize(claims)

            print("TOTAL AFTER UPLOAD:", size+gallery_size, "MB")

            if size+gallery_size > MAX_STORAGE_SIZE:
                session['error_message'] = "Storage size exceeded, please delete some images"
                return redirect('/gallery?gallery_name='+gallery_name)

            if file.filename == '' or gallery_name == '':
                session['error_message'] = "Invalid gallery name"
                return redirect('/gallery?gallery_name='+gallery_name)
    
            # valide file extension to be JPEG or PNG
            split_tup = file.filename.split('.')
            file_extension = split_tup[len(split_tup) -1].lower()
            
            if file_extension != 'jpeg' and file_extension != 'jpg' and file_extension != 'png':
                session['error_message'] = "Invalid file type"
                return redirect('/gallery?gallery_name='+gallery_name)

            addFile(file, gallery_name, claims)
            session['success_message'] = "Image uploaded"
    
        except ValueError as exc:
            session['error_message'] = str(exc)

    return redirect('/gallery?gallery_name='+gallery_name)

# POST route to delete an image
# request form
# file_path: the full path of the image file in the firebase storage
# gallery_name: name of the gallery in which the image resides
@app.route('/delete_file', methods=['post'])
def deleteFileHandler():
    id_token = request.cookies.get("token")

    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
            
            file_path = request.form['file_path']
            gallery_name = request.form['gallery_name']

            if claims['user_id'] not in file_path or gallery_name == '':
                session['error_message'] = "Invalid operation"
                return redirect('/gallery?gallery_name='+gallery_name)

            deleteFile(file_path)
            session['success_message'] = "Image deleted"
        
        except ValueError as exc:
            session['error_message'] = str(exc)

    return redirect('/gallery?gallery_name='+gallery_name)

# POST route to update user info
# request form
# name: name of the user
@app.route('/edit_user_info', methods=['POST'])
def editUserInfo():
    id_token = request.cookies.get("token")
    claims = None

    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
            new_name = request.form['name']
            updateUserInfo(claims, new_name)
            session['success_message'] = "User info updated"
        except ValueError as exc:
            session['error_message'] = str(exc)
    return redirect("/")

# create userinfo in the google cloud data store
def createUserInfo(claims):
    entity_key = datastore_client.key('UserInfo', claims['email'])
    entity = datastore.Entity(key = entity_key)
    entity.update({
        'email': claims['email'],
        'name': "",
        'user_id': claims['user_id']
    })
    datastore_client.put(entity)
    addDirectory(claims)

# get user into from the google cloud data store provided the loggedin user's email
def retrieveUserInfo(claims):
    entity_key = datastore_client.key('UserInfo', claims['email'])
    entity = datastore_client.get(entity_key)
    return entity

# update the providded info in the google cloud data store userInfo entity
def updateUserInfo(claims, new_name):
    entity_key = datastore_client.key('UserInfo', claims['email'])
    entity = datastore_client.get(entity_key)
    entity.update({
        'name': new_name,
        'user_id': claims['user_id']
    })
    datastore_client.put(entity)

# add a directory in the firebase storage named as the firebase user auth id for isolation
def addDirectory(claims):
    storage_client = storage.Client(project=local_constants.PROJECT_NAME)
    bucket = storage_client.bucket(local_constants.PROJECT_STORAGE_BUCKET)
    blob = bucket.blob(claims['user_id']+"/")
    blob.upload_from_string('', content_type='application/x-www-formurlencoded;charset=UTF-8')

# add a directory within the isolated user directory to prevent overlaping
def addGallery(gallery_name, claims):
    storage_client = storage.Client(project=local_constants.PROJECT_NAME)
    bucket = storage_client.bucket(local_constants.PROJECT_STORAGE_BUCKET)
    blob = bucket.blob(claims['user_id']+"/"+gallery_name+"/")
    blob.upload_from_string('', content_type='application/x-www-formurlencoded;charset=UTF-8')

# remove the provede directory i.e gallery
def deleteGallery(gallery_name):
    storage_client = storage.Client(project=local_constants.PROJECT_NAME)
    bucket = storage_client.bucket(local_constants.PROJECT_STORAGE_BUCKET)
    blob = bucket.blob(gallery_name)
    blob.delete()

# add a file to the firebase storage provided the whole path
# convention:
# <user_id>/<gallery_name>/<filename>
def addFile(file, gallery_name, claims):
    storage_client = storage.Client(project=local_constants.PROJECT_NAME)
    bucket = storage_client.bucket(local_constants.PROJECT_STORAGE_BUCKET)
    blob = bucket.blob(claims['user_id']+"/"+gallery_name+"/"+file.filename)
    blob.upload_from_file(file)

# delete the file from firebase storage provided the full path
def deleteFile(file_name):
    storage_client = storage.Client(project=local_constants.PROJECT_NAME)
    bucket = storage_client.bucket(local_constants.PROJECT_STORAGE_BUCKET)
    blob = bucket.blob(file_name)
    blob.delete()

# calculate the loggedin user's isolated directory size
def getGallerySize(claims):
    storage_size = 0

    blob_list = blobList(claims['user_id']+"/")
    bucket = getBucket()

    for i in blob_list:
        blob_path = i.name
        blob = bucket.get_blob(blob_path)
        storage_size = storage_size+blob.size

    storage_size = storage_size/1000000
    storage_size = round(storage_size, 2)

    return storage_size

# get the list of blobs residing in the firebase storage bucket
def blobList(prefix):
    storage_client = storage.Client(project=local_constants.PROJECT_NAME)
    return storage_client.list_blobs(local_constants.PROJECT_STORAGE_BUCKET, prefix=prefix)

# get the firebase storage bucket 
def getBucket():
    storage_client = storage.Client(project=local_constants.PROJECT_NAME)
    bucket = storage_client.get_bucket(local_constants.PROJECT_STORAGE_BUCKET)

    return bucket
    
if __name__ == '__main__':
    # This is used when running locally only. When deploying to Google App
    # Engine, a webserver process such as Gunicorn will serve the app. This
    # can be configured by adding an `entrypoint` to app.yaml.
    # Flask's development server will automatically serve static files in
    # the "static" directory. See:
    # http://flask.pocoo.org/docs/1.0/quickstart/#static-files. Once deployed,
    # App Engine itself will serve those files as configured in app.yaml.
    app.run(host='127.0.0.1', port=8080, debug=True)
# [END gae_python3_render_template]
# [END gae_python38_render_template]
