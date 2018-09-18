import requests
import flask
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from datetime import datetime
from dateutil import tz
import json
import logging
import itertools

# Use the application default credentials
cred = credentials.ApplicationDefault()
firebase_admin.initialize_app(cred, {
  'projectId': 	'todoisthabiticasync-216323',
})

# cred = credentials.Certificate('/Users/mtwichel/Google Drive/Documents/Development/Projects/other/TodoistHabiticaIntegration/functions/TodoistHabiticaSync-075884dae0fc.json')
# default_app = firebase_admin.initialize_app(cred)


def authorizeTodoistApp(request):
    db = firestore.client()

    code = request.args.get('code')
    state = request.args.get('state')
    data = {'client_id':'310591571acd4a20ac5616665445f52f',
        'client_secret':'1611f1f32fed45bd87b4d6f0269f9de1',
        'code':code}
    
    if state == 'yodarox314':
        authRequest = requests.post('https://todoist.com/oauth/access_token', data=data)
        userToken = authRequest.json().get('access_token')
        idRequest = requests.post('https://todoist.com/api/v7/sync', data={'token':userToken, 'sync_token': '*', 'resource_types': '["user"]'})
        print(idRequest.json())
        userId = idRequest.json().get('user').get('id')
        db.document('users/' + str(userId)).set({'todoistAuthToken' : userToken})
        return 'All Good'
    else:
        #abandon ship
        return abort(403)

def getTodoistAuthToken(userId):
    db = firestore.client()
    return db.document('users/' + str(userId)).get().to_dict().get('todoistAuthToken')

def getHabiticaAuth(userId):
    db = firestore.client()
    json = db.document('users/' + str(userId)).get().to_dict()
    habiticaAuth = {
        'x-api-user' : json.get('habiticaUserId'),
        'x-api-key' : json.get('habiticaApiToken'),
        'Content-Type' : 'application/json'
    }
    return habiticaAuth
    
    

def addLabelToDbFromTodoist(userId, todoistId):
    db = firestore.client()
    userToken = getTodoistAuthToken(userId)

    # get text from todoist label 
    labelRequest = requests.get(('https://beta.todoist.com/API/v8/labels/' + str(todoistId)), headers={'Authorization' : 'Bearer ' + userToken})
    text = labelRequest.json().get('name')

    # add tag to habitica
    headers = getHabiticaAuth(userId)
    tagRequest = requests.post('https://habitica.com/api/v3/tags', headers=headers, data='{"name":"@'+ text +'"}')
    habiticaGuid = tagRequest.json().get('data').get('id')

    db.collection('users').document(str(userId)).collection('labels').document().set({
        'todoistId' : todoistId,
        'text' : text,
        'habiticaGuid' : habiticaGuid
        })
    return habiticaGuid

def addProjectToDbFromTodoist(userId, todoistId):
    db = firestore.client()
    userToken = getTodoistAuthToken(userId)

    # get text from todoist label 
    labelRequest = requests.get(('https://beta.todoist.com/API/v8/projects/' + str(todoistId)), headers={'Authorization' : 'Bearer ' + userToken})
    text = labelRequest.json().get('name')

    # add tag to habitica
    headers = getHabiticaAuth(userId)
    tagRequest = requests.post('https://habitica.com/api/v3/tags', headers=headers, data='{"name":"#'+ text +'"}')
    habiticaGuid = tagRequest.json().get('data').get('id')

    doc = db.collection('users').document(str(userId)).collection('projects').document()
    doc.set({
        'todoistId' : todoistId,
        'text' : text,
        'habiticaGuid' : habiticaGuid
        })
    return habiticaGuid

def convertToLocalTime(dueDateUtc):
    utc = datetime.strptime(dueDateUtc, '%a %d %b %Y %H:%M:%S %z')
    utc = utc.replace(tzinfo=tz.tzutc())
    local = utc.astimezone(tz.gettz('America/Denver')) 
    return local
def convertPriority(todoistPriority):
    switcher = {
        1: 0.1,
        2: 1,
        3: 1.5,
        4: 2
    }
    return switcher.get(todoistPriority)


def processTodoistWebhook(request):
    db = firestore.client()

    request_json = request.get_json()
    
    if request_json.get('event_name') == 'item:added':

        #Item added

        # get all the data needed from json object
        initiator = request_json.get('initiator')
        eventData = request_json.get('event_data')
        
        userId = initiator.get('id')
        text = eventData.get('content')
        projectId = eventData.get('project_id')
        labels = eventData.get('labels')
        dueDateUtc = eventData.get('due_date_utc') 
        priority = eventData.get('priority') 

        #convert date from utc to local if needed
        if(dueDateUtc != None):
            localDate = convertToLocalTime(dueDateUtc)
        else:
            localDate = None

        # get labels from db, and create if needed
        tags = []
        for labelId in labels:
            handeled = False
            docs = db.collection('users/' + str(userId) + '/labels').where('todoistId', '==', labelId).get()
            for doc in docs:
                tags.append(doc.to_dict().get('habiticaGuid'))
                handeled = True
            if not handeled:
                print('Adding label' + str(labelId) + ' to the db')
                tags.append(addLabelToDbFromTodoist(userId, labelId))

        # get project from db, and create if needed
        projects = db.collection('users/' + str(userId) + '/projects').where('todoistId', '==', projectId).get()
        handeled = False
        for project in projects:
            #already in DB
            tags.append(project.to_dict().get('habiticaGuid'))
            handeled = True
        if not handeled:
            print('Adding project' + str(projectId) + ' to the db')
            tags.append(addProjectToDbFromTodoist(userId, projectId))
           

        #build request to add to habitica
        habiticaRequestData = {
            'text' : text,
            'type' : 'todo',
            'tags' : str(tags),
            'priority' : convertPriority(priority)}
        if localDate != None:
            habiticaRequestData.update({'date': str(localDate)})

        habiticaAuth = getHabiticaAuth(userId)

        habiticaRequest = requests.post('https://habitica.com/api/v3/tasks/user', 
            data=json.dumps(habiticaRequestData), 
            headers=habiticaAuth)
        if not habiticaRequest.json().get('success'):
            print(str(tags))
            logging.warn(habiticaRequest.json().get('message'))
            logging.warn(habiticaRequest.json().get('errors')[0].get('message'))