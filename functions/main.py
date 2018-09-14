import requests
import flask

def authorizeTodoistApp(request):
    code = request.args.get('code')
    state = request.args.get('state')
    data = {'client_id':'310591571acd4a20ac5616665445f52f',
        'client_secret':'1611f1f32fed45bd87b4d6f0269f9de1',
        'code':code}
    
    if state == 'yodarox314':
        requests.post('https://todoist.com/oauth/access_token', data=data)
        return 'All Good'
    else:
        #abandon ship
        return abort(403)


def processTodoistWebhook(request):
    request_json = request.get_json()
    print(request_json.get('event_name'))
    
    if(request_json.get('event_name') == 'item.added'):
        #Item added
        eventData = request_json.get('event_data')
        print(eventData)
        
        projectId = eventData.get('project_id')
        labels = eventData.get('labels')


        #check it it's labels are in the system
        #for label in labels:
            #TODO Cycle through labels and make sure they're in the database

        #TODO check if projectId is in the system
        
    return "hi"
    
