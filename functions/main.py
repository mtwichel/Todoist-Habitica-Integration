import requests
import flask
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

# Use the application default credentials
cred = credentials.ApplicationDefault()
firebase_admin.initialize_app(cred, {
  'projectId': 	'todoisthabiticasync-216323',
})


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
        idRequest = requests.post('https://todoist.com/api/v7/sync', data={'token':userToken, 'sync_token': '*', 'resource_types': ['user']})
        id = idRequest.json().get('id')
        db.document('users/' + str(id)).set({'todoistAuthToken' : userToken})
        return 'All Good'
    else:
        #abandon ship
        return abort(403)


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
            "labels": [1135, 5532],
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
        projectId = eventData.get('project_id')
        labels = eventData.get('labels')


        # check it it's labels are in the system
        for label in labels:
            docs = db.collection('users/' + str(userId) + '/labels').where('todoistId', '==', str(label)).get()
            for doc in docs:
                if(doc != None):
                    # Need to add it
                    print('hi')
                else:
                    # Already in the system
                    print('hi')
        
    

processTodoistWebhook(None)
