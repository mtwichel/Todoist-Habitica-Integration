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
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Habitica Integration</title>
        </head>
        <body>
            <style>
            * {
                margin: 10px;
            }
            </style>
            <h2>Your Todoist API ID:</h2><p id='todoistApi'>"""+str(userId)+"""</p>
            <label for='#apiGuid'>Personal UUID: </label>
            <input id='apiGuid'>
            <br>
            <label for='#apiGuid'>Personal API Key: </label>
            <input id='apiKey'>
            <br>
            <button type='submit' id='submit'>Submit</button>
            <br>
            <a href='http://habitica.wikia.com/wiki/API_Options'>Find More Information Here!</a>
            <script src="https://ajax.googleapis.com/ajax/libs/jquery/3.3.1/jquery.min.js"></script>
            <script>
            $('#submit').click(function(){
                var uuid = $('#apiGuid').val()
                var key = $('#apiKey').val()
                var todoistApi = $('#todoistApi').text()
                window.location.href = ('https://us-central1-todoisthabiticasync-216323.cloudfunctions.net/addHabiticaApiCreds?' + 'apiGuid=' + uuid +'&apiKey='+key + '&todoistId='+ todoistApi);
            });
            
            </script>
        </body>
        </html>
        """
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

    request_json = request.get_json()
    
    if request_json.get('event_name') == 'item:added':
        processItemAdded(request_json)
    elif request_json.get('event_name') == 'item:completed':
        processItemCompleted(request_json)
    elif request_json.get('event_name') == 'item:updated':
        processItemUpdated(request_json)
    elif request_json.get('event_name') == 'item:deleted':
        processItemDeleted(request_json)

def checkLabelsInDb(labels, userId):
    db=firestore.client()

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
    return tags

def checkProjectInDb(userId, projectId):
    db=firestore.client()
    projects = db.collection('users/' + str(userId) + '/projects').where('todoistId', '==', projectId).get()
    handeled = False
    for project in projects:
        #already in DB
        return project.to_dict().get('habiticaGuid')
        handeled = True
    if not handeled:
        print('Adding project' + str(projectId) + ' to the db')
        return addProjectToDbFromTodoist(userId, projectId)

def processItemAdded(request_json):
    db = firestore.client()

    # get all the data needed from json object
    initiator = request_json.get('initiator')
    eventData = request_json.get('event_data')

    userId = initiator.get('id')
    taskId = eventData.get('id')
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
    tags = checkLabelsInDb(labels, userId)

    # get project from db, and create if needed
    tags.append(checkProjectInDb(userId, projectId))


    #build request to add to habitica
    habiticaRequestData = {
        'text' : text,
        'type' : 'todo',
        'tags' : tags,
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
    else:
        habiticaTaskId = habiticaRequest.json().get('data').get('id')
        db.collection('users').document(str(userId)).collection('tasks').document().set({
        'todoistId' : taskId,
        'text' : text,
        'habiticaGuid' : habiticaTaskId
        })

def processItemCompleted(request_json):
    db = firestore.client()
    taskId=request_json.get('event_data').get('id')
    userId=request_json.get('initiator').get('id')

    count = 0
    tasks = db.collection('users').document(str(userId)).collection('tasks').where('todoistId', '==', taskId).get()
    for task in tasks:
        count += 1
        if count == 1:
            habiticaGuid = task.to_dict().get('habiticaGuid')
        elif count == 0:
            logging.warn('task '+taskId+' not found')
        else:
            logging.warn('to many tasks with id '+ taskId+' found')

    headers = getHabiticaAuth(userId)

    requests.post('https://habitica.com/api/v3/tasks/'+habiticaGuid +'/score/up', headers=headers)

def processItemUpdated(request_json):
    db = firestore.client()

    # get all the data needed from json object
    initiator = request_json.get('initiator')
    eventData = request_json.get('event_data')

    userId = initiator.get('id')
    taskId = eventData.get('id')
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
    tags = checkLabelsInDb(labels, userId)

    # get project from db, and create if needed
    tags.append(checkProjectInDb(userId, projectId))


    #build request to add to habitica
    habiticaRequestData = {
        'text' : text,
        'type' : 'todo',
        'tags' : tags,
        'priority' : convertPriority(priority)}
    if localDate != None:
        habiticaRequestData.update({'date': str(localDate)})

    headers = getHabiticaAuth(userId)
    count = 0
    tasks = db.collection('users').document(str(userId)).collection('tasks').where('todoistId', '==', taskId).get()
    for task in tasks:
        count += 1
        if count == 1:
            habiticaGuid = task.to_dict().get('habiticaGuid')
        elif count == 0:
            logging.warn('task '+taskId+' not found')
        else:
            logging.warn('to many tasks with id '+ taskId+' found')

    habiticaRequest = requests.put('https://habitica.com/api/v3/tasks/' + habiticaGuid, 
        data=json.dumps(habiticaRequestData), 
        headers=headers)

    if not habiticaRequest.json().get('success'):
        print(str(tags))
        logging.warn(habiticaRequest.json().get('message'))
        logging.warn(habiticaRequest.json().get('errors')[0].get('message'))

def processItemDeleted(request_json):
    db = firestore.client()
    taskId=request_json.get('event_data').get('id')
    userId=request_json.get('initiator').get('id')

    count = 0
    tasks = db.collection('users').document(str(userId)).collection('tasks').where('todoistId', '==', taskId).get()
    for task in tasks:
        count += 1
        if count == 1:
            habiticaGuid = task.to_dict().get('habiticaGuid')
        elif count == 0:
            logging.warn('task '+taskId+' not found')
        else:
            logging.warn('to many tasks with id '+ taskId+' found')

    headers = getHabiticaAuth(userId)

    requests.delete('https://habitica.com/api/v3/tasks/'+habiticaGuid, headers=headers)