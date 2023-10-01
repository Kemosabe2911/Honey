import slack
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, request, Response
from slackeventsapi import SlackEventAdapter
import threading
import schedule
import time

from config import GetSlackToken, GetSlackSigningSecret

from db import FetchPersonalLinks, FetchPersonalDocuments
from internal.social import PerformSocialLinkOperation
from internal.document import PerformDocumentsOperation
from utils.common import FetchChannelName
from utils.consts import ChatGPTChannelName
from utils.chatgpt import CallChatGPTAI

# set env path
env_path = Path('.') / '.env'
load_dotenv(dotenv_path=env_path)

app = Flask(__name__)
slack_event_adapter = SlackEventAdapter(GetSlackSigningSecret(), '/slack/events', app)

client = slack.WebClient(token=GetSlackToken())
BOT_ID = client.api_call("auth.test")['user_id']
# client.chat_postMessage(channel='#test', text="Hello World!")

message_counts = {}

@app.route("/slack/events", methods=["GET", "POST"])
def handle_slack_events():
    if request.method == "GET":
        challenge = request.args.get("challenge")
        return challenge, 200

    # Handle other events using the POST method
    # data = request.get_json()
    # print(data)
    # if "event" in data:
    #     event = data["event"]
    #     event_type = event.get("type")

    #     if event_type == "message":
    #         channel = event.get("channel")
    #         text = event.get("text")
    #         user = event.get("user")

    #         if BOT_ID != user:
    #             # Add your logic to handle the message event
    #             # For example, you can print the message details
    #             print(f"Received message: '{text}' in channel: {channel} from user: {user}")
    #             client.chat_postMessage(channel=channel, text=text)
    
    return "", 200

@slack_event_adapter.on('message')
def message(payload):
    event= payload.get('event', {})
    channel = event.get('channel')
    user = event.get('user')
    text = event.get('text')

    channel_name = FetchChannelName(client=client, channel_id=channel)

    if channel_name == ChatGPTChannelName:
        message = CallChatGPTAI(input_text=text)
        print(f"Received message: '{message}'")
        client.chat_postMessage(channel=channel, text=message)

    if BOT_ID != user:
        # Add your logic to handle the message event
        # For example, you can print the message details
        print(f"Received message: '{text}' in channel: {channel_name} from user: {user}")
        if user in message_counts:
            message_counts[user] += 1
        else:
            message_counts[user] = 1
        client.chat_postMessage(channel=channel, text=text)

@app.route('/message-count', methods=['POST'])
def message_count():
    data = request.form
    user_id = data.get('user_id')
    channel_id = data.get('channel_id')
    message_count = message_counts.get(user_id, 0)
    client.chat_postMessage(channel=channel_id, text=f"Message: {message_count}")
    
    return Response(), 200

@app.route('/social', methods=['POST'])
def social():
    data = request.form
    user_id = data.get('user_id')
    channel_id = data.get('channel_id')
    text = data.get('text')
    
    socialDataList = text.split()
    if len(socialDataList) > 1 :
        PerformSocialLinkOperation(
            user=user_id,
            channel=channel_id,
            data=socialDataList
        )
        client.chat_postMessage(channel=channel_id, text=f"Message: operation success")
    else:
        list = FetchPersonalLinks(
            user= user_id,
            channel=channel_id
        )
        if list == None:
            client.chat_postMessage(channel=channel_id, text=f"No data to display")
        else:
            for v in list:
                client.chat_postMessage(channel=channel_id, text=f"{v.source}: {v.link}")
    
    return Response(), 200

@app.route('/doc', methods=['POST'])
def Documents():
    data = request.form
    user_id = data.get('user_id')
    channel_id = data.get('channel_id')
    text = data.get('text')
    
    docDataList = text.split()
    if len(docDataList) > 1 :
        PerformDocumentsOperation(
            user=user_id,
            channel=channel_id,
            data=docDataList
        )
        client.chat_postMessage(channel=channel_id, text=f"Message: operation success")
    else:
        list = FetchPersonalDocuments(
            user= user_id,
            channel=channel_id
        )
        if list == None:
            client.chat_postMessage(channel=channel_id, text=f"No data to display")
        else:
            for v in list:
                client.chat_postMessage(channel=channel_id, text=f"{v.source}: {v.link}")
    
    return Response(), 200

def job():
    print("Job is running...")

def scheduled_job():
    while True:
        schedule.run_pending()
        time.sleep(1)

# Schedule a job to run every 5 minutes
schedule.every(5).minutes.do(job)

# Create a thread for the scheduled job
scheduled_job_thread = threading.Thread(target=scheduled_job)

# Start the scheduled job thread in the background
scheduled_job_thread.start()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
