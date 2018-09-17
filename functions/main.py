import requests
import flask
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from datetime import datetime
from dateutil import tz
import json

# Use the application default credentials
# cred = credentials.ApplicationDefault()
# firebase_admin.initialize_app(cred, {
#   'projectId': 	'todoisthabiticasync-216323',
# })

cred = credentials.Certificate('/Users/mtwichel/Google Drive/Documents/Development/Projects/other/TodoistHabiticaIntegration/functions/TodoistHabiticaSync-075884dae0fc.json')
default_app = firebase_admin.initialize_app(cred)


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
    tagRequest = requests.post('https://habitica.com/api/v3/tags', headers=headers, data='{"name":"'+ text +'"}')
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

    db.collection('users').document(str(userId)).collection('projects').document().set({
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

    #request_json = request.get_json()
    request_json = {
        "event_name": "item:added",
        "initiator": {
            "is_premium": True,
            "image_id": "e33bf67084c8b1d35b12c8b2e93ae765",
            "id": 3185441,
            "full_name": "Marcus Twichel",
            "email": "marc.twichy@gmail.com"
        },
        "version": "7",
        "user_id": 3185441,
        "event_data": {
            "assigned_by_uid": None,
            "is_archived": 0,
            "labels": [],
            "sync_id": None,
            "all_day": False,
            "in_history": 0,
            "indent": 1,
            "checked": 0,
            "date_completed": None,
            "date_lang": None,
            "id": 2813975481,
            "content": "test2",
            "is_deleted": 0,
            "date_added": "Fri 14 Sep 2018 06:17:48 +0000",
            "user_id": 3185441,
            "url": "https://todoist.com/showTask?id=2813975481",
            "due_date_utc": None,
            "priority": 1,
            "parent_id": None,
            "item_order": 2,
            "responsible_uid": None,
            "project_id": 2194594717,
            "collapsed": 0,
            "date_string": None
        }
    }
    
    if request_json.get('event_name') == 'item:added':

        #Item added
        initiator = request_json.get('initiator')
        eventData = request_json.get('event_data')
        
        userId = initiator.get('id')
        text = eventData.get('content')
        projectId = eventData.get('project_id')
        labels = eventData.get('labels')
        dueDateUtc = eventData.get('due_date_utc') 
        priority = eventData.get('priority') 

        if(dueDateUtc != None):
            localDate = convertToLocalTime(dueDateUtc)
        else:
            localDate = None

        # get labels
        tags = []
        for labelId in labels:
            docs = db.collection('users/' + str(userId) + '/labels').where('todoistId', '==', str(labelId)).get()
            for doc in docs:
                if doc == None:
                    # Need to add it
                    tags.append(addLabelToDbFromTodoist(userId, labelId))
                else:
                    # Already in the system
                    tags.append(doc.to_dict().get('habiticaGuid'))

        # get project
        projects = db.collection('users/' + str(userId) + '/projects').where('projectId', '==', str(projectId)).get()
        for project in projects:
            if project==None:
                # add project to DB
                tags.append(addProjectToDbFromTodoist(userId, projectId))
            else:
                tags.append(project.to_dict().get('habiticaGuid'))
        
        habiticaRequestData = {
            'text' : text,
            'type' : 'todo',
            'tags' : tags,
            'priority' : convertPriority(priority)}
        if localDate != None:
            habiticaRequestData.update({'date': localDate})

        habiticaAuth = getHabiticaAuth(userId)

        habiticaRequest = requests.post('https://habitica.com/api/v3/tasks/user', 
            data=json.dumps(habiticaRequestData), 
            headers=habiticaAuth)
        