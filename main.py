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

@app.route('/')
def root():
    id_token = request.cookies.get("token")
    error_message = None
    success_message = None
    claims = None
    user_info = None
    gallery_list = []

    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
            
            user_info = retrieveUserInfo(claims)

            if user_info == None:
                createUserInfo(claims)
                user_info = retrieveUserInfo(claims)

            blob_list = blobList(None)
            bucket = getBucket()
            for i in blob_list:
                blob_path = i.name
                blob = bucket.blob(blob_path)
                print(blob)

                # check if file or directory belongs to user
                # valide file extension to be JPEG or PNG
                split_tup = i.name.split('/')
                directory_prefix = split_tup[0]

                print(split_tup, split_tup[len(split_tup)-1])

                if directory_prefix == claims['user_id']:
                    if len(split_tup) > 2 and i.name[len(i.name) - 1] == '/':
                        i.gallery_name = split_tup[len(split_tup)-2]
                        gallery_list.append(i)

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
        gallery_list=gallery_list
    )


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
        gallery_name=gallery_name
    )

@app.route('/delete_directory', methods=['POST'])
def deleteGalleryHandler():
    id_token = request.cookies.get("token")
    claims = None
    
    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
            gallery_name = request.form['dir_name']

            if gallery_name == '':
                session['error_message'] = "Invalid gallery name"
                return redirect('/')
            
            if gallery_name[len(gallery_name) - 1] != '/':
                gallery_name = gallery_name+"/"

            user_info = retrieveUserInfo(claims)
            deleteGallery(gallery_name, user_info)
            session['success_message'] = "Gallery deleted"
        
        except ValueError as exc:
            session['error_message'] = str(exc)
    return redirect('/')

@app.route('/upload_file', methods=['post'])
def uploadFileHandler():
    id_token = request.cookies.get("token")
    claims = None

    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
            file = request.files['file_name']
            gallery_name = request.form['gallery_name']
    
            if file.filename == '' or gallery_name == '':
                session['error_message'] = "Invalid gallery name"
                return redirect('/')
    
            # valide file extension to be JPEG or PNG
            split_tup = file.filename.split('.')
            file_extension = split_tup[len(split_tup) -1].lower()
            
            if file_extension != 'jpeg' and file_extension != 'jpg' and file_extension != 'png':
                session['error_message'] = "Invalid file type"
                return redirect('/')

            addFile(file, gallery_name, claims)
            session['success_message'] = "Image uploaded"
    
        except ValueError as exc:
            session['error_message'] = str(exc)

    return redirect('/gallery?gallery_name='+gallery_name)

@app.route('/delete_file', methods=['post'])
def deleteFileHandler():
    id_token = request.cookies.get("token")

    if id_token:
        try:
            claims = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
            
            gallery_name = request.form['gallery_name']
            file_path = request.form['file_path']

            if claims['user_id'] not in file_path or gallery_name == '':
                session['error_message'] = "Invalid operation"
                return redirect('/gallery?gallery_name='+gallery_name)

            deleteFile(file_path)
            session['success_message'] = "Image deleted"
        
        except ValueError as exc:
            session['error_message'] = str(exc)

    return redirect('/gallery?gallery_name='+gallery_name)

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

def retrieveUserInfo(claims):
    entity_key = datastore_client.key('UserInfo', claims['email'])
    entity = datastore_client.get(entity_key)
    return entity

def updateUserInfo(claims, new_name):
    entity_key = datastore_client.key('UserInfo', claims['email'])
    entity = datastore_client.get(entity_key)
    entity.update({
        'name': new_name,
        'user_id': claims['user_id']
    })
    datastore_client.put(entity)

def addDirectory(claims):
    storage_client = storage.Client(project=local_constants.PROJECT_NAME)
    bucket = storage_client.bucket(local_constants.PROJECT_STORAGE_BUCKET)
    blob = bucket.blob(claims['user_id']+"/")
    blob.upload_from_string('', content_type='application/x-www-formurlencoded;charset=UTF-8')

def addGallery(gallery_name, claims):
    storage_client = storage.Client(project=local_constants.PROJECT_NAME)
    bucket = storage_client.bucket(local_constants.PROJECT_STORAGE_BUCKET)
    blob = bucket.blob(claims['user_id']+"/"+gallery_name+"/")
    blob.upload_from_string('', content_type='application/x-www-formurlencoded;charset=UTF-8')

def deleteGallery(gallery_name):
    storage_client = storage.Client(project=local_constants.PROJECT_NAME)
    bucket = storage_client.bucket(local_constants.PROJECT_STORAGE_BUCKET)
    blob = bucket.blob(gallery_name)
    blob.delete()

def addFile(file, gallery_name, claims):
    storage_client = storage.Client(project=local_constants.PROJECT_NAME)
    bucket = storage_client.bucket(local_constants.PROJECT_STORAGE_BUCKET)
    blob = bucket.blob(claims['user_id']+"/"+gallery_name+"/"+file.filename)
    blob.upload_from_file(file)

def deleteFile(file_name):
    storage_client = storage.Client(project=local_constants.PROJECT_NAME)
    bucket = storage_client.bucket(local_constants.PROJECT_STORAGE_BUCKET)
    blob = bucket.blob(file_name)
    blob.delete()

def downloadBlob(filename):
    storage_client = storage.Client(project=local_constants.PROJECT_NAME)
    bucket = storage_client.bucket(local_constants.PROJECT_STORAGE_BUCKET)
    blob = bucket.blob(filename)
    return blob.download_as_bytes()

def blobList(prefix):
    storage_client = storage.Client(project=local_constants.PROJECT_NAME)
    return storage_client.list_blobs(local_constants.PROJECT_STORAGE_BUCKET, prefix=prefix)

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
