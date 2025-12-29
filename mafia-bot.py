import slack
import requests
from flask import Flask, request, Response #jsonify
from slackeventsapi import SlackEventAdapter
# from slack_bolt import App
# from slack_bolt.adapter.flask import SlackRequestHandler

vote_dict = {}
players_voted = {}
phase = False # True = Day, False = Night

# Initialize Flask app and Slack app
app = Flask(__name__)
slack_event_adapter = SlackEventAdapter(SIGNING_SECRET,'/slack/events', app)

client = slack.WebClient(
                token=SLACK_TOKEN)
BOT_ID = client.api_call("auth.test")['user_id']

def get_bot_channel():
    channels = client.conversations_list()['channels']
    for channel in channels:
        if channel['name'] == 'bot-commands':
            return channel['id']
    else:
        return None

@app.route('/vote', methods=['GET','POST'])
def vote():
    data = request.form
    print(data)
    user_id = data.get('user_id')
    user_name = data.get('user_name')
    text = data.get('text')
    channel_id = data.get('channel_id')
    channel_name = data.get('channel_name')

    print(phase, channel_name)
    if (phase and channel_name == 'main-chat') or (not phase and channel_name == 'koopa-troop'):
        player_vote(user_id, user_name, text, channel_id)
    elif channel_name == 'moderators':
        mod_vote(user_id, user_name, text, channel_id)
    else:
        client.chat_postEphemeral(channel=channel_id, user=user_id, text="It's not the right time/place to use this command! You may only vote in #main-chat during the day, or in #koopa-troop during the night if you are a member of the mafia. Right now the phase is " + \
                                  ("Day." if phase else "Night."))
    return Response(), 200

def player_vote(user_id, user_name, text, channel_id):
    """
    Vote cast by player.
    """
    voted_before = None
    if user_id in players_voted:
        voted_before = players_voted[user_id][1]    
    players_voted[user_id] = (user_name, text)

    if text not in vote_dict:
        vote_dict[text] = 1
    else:
        vote_dict[text] += 1

    if not voted_before:
        client.chat_postMessage(channel=channel_id, text=" " + user_name + " voted for " + text + ", Current votes = " + str(vote_dict[text]))
        
        client.chat_postMessage(channel=get_bot_channel(), text=" " + user_name + " voted for " + text + ", Current votes = " + str(vote_dict[text]))
    else:
        if vote_dict[voted_before] == 1:
            del vote_dict[voted_before]
        else:
            vote_dict[voted_before] -= 1
        client.chat_postMessage(channel=channel_id, text=" " + user_name + " changed their vote to " + text + ", Current votes = " + str(vote_dict[text]))
        client.chat_postMessage(channel=get_bot_channel(), text=" " + user_name + " changed their vote to " + text + ", Current votes = " + str(vote_dict[text]))

def mod_vote(user_id, user_name, text, channel_id):
    """
    Vote cast by moderator.
    """
    if text not in vote_dict:
        vote_dict[text] = 1
    else:
        vote_dict[text] += 1

    client.chat_postMessage(channel=channel_id, text=" " + user_name + " voted for " + text + ", current votes = " + str(vote_dict[text]))

def vote_count_to_str():
    sorted_dict = sorted(vote_dict.items(), key=lambda x: x[1], reverse=True)
    print_str = "The current votes are: \n"
    for name, count in sorted_dict:
        print_str += "" + name + ": " + str(count) + "\n"
    return print_str

@app.route('/removevote', methods=['GET','POST'])
def remove_vote():
    data = request.form
    print(data)
    user_id = data.get('user_id')
    user_name = data.get('user_name')
    text = data.get('text')
    channel_id = data.get('channel_id')
    channel_name = data.get('channel_name')

    print(phase, channel_name)
    if (phase and channel_name == 'main-chat') or (not phase and channel_name == 'koopa-troop'):
        player_remove(user_id, user_name, text, channel_id)
    elif channel_name == 'moderators':
        mod_remove(user_id, user_name, text, channel_id)
    else:
        client.chat_postEphemeral(channel=channel_id, user=user_id, text="It's not the right time/place to use this command! You may only remove your vote in #main-chat during the day, or in #koopa-troop during the night if you are a member of the mafia. Right now the phase is " + \
                                  ("Day." if phase else "Night."))
    return Response(), 200

def player_remove(user_id, user_name, text, channel_id):
    """
    Vote cast by player.
    """
    voted_before = None
    if user_id in players_voted:
        voted_before = players_voted[user_id][1]    
        del players_voted[user_id]

        client.chat_postMessage(channel=channel_id, text=" " + user_name + " removed their vote for " + voted_before + ", Current votes = " + str(vote_dict[voted_before] - 1))
        
        if vote_dict[voted_before] == 1:
            del vote_dict[voted_before]
        else:
            vote_dict[voted_before] -= 1
        
    else:
        client.chat_postEphemeral(channel=channel_id, user=user_id, text="You have not previously cast a vote during this phase.")

def mod_remove(user_id, user_name, text, channel_id):
    """
    Vote cast by moderator.
    """
    if text in vote_dict:
        vote_dict[text] -= 1
    client.chat_postMessage(channel=channel_id, text=" " + user_name + " removed a vote for " + text + ", current votes = " + str(vote_dict[text]))


@app.route('/currentvotes', methods=['GET','POST'])
def currentvotes():
    data = request.form
    user_id = data.get('user_id')
    user_name = data.get('user_name')
    channel_id = data.get('channel_id')
    channel_name = data.get('channel_name')

    if (phase and channel_name == 'main-chat') or (not phase and channel_name == 'koopa-troop') or (channel_name == 'moderators'):
        client.chat_postEphemeral(channel=channel_id, user=user_id, text=vote_count_to_str())
    else:
        client.chat_postEphemeral(channel=channel_id, user=user_id, text="It's not the right time/place to use this command! You may only view the current votes in #main-chat during the day, or in #koopa-troop during the night if you are a member of the mafia. Right now the phase is " + \
                                  ("Day." if phase else "Night."))
    
    print(data)
    return Response(), 200

def final_vote_to_str():
    sorted_dict = sorted(vote_dict.items(), key=lambda x: x[1], reverse=True)
    print_str = "The final votes are: \n"
    for name, count in sorted_dict:
        print_str += "" + name + ": " + str(count) + "\n"
    return print_str

@app.route('/endphase', methods=['GET','POST'])
def endphase():
    data = request.form
    user_id = data.get('user_id')
    user_name = data.get('user_name')
    channel_id = data.get('channel_id')
    channel_name = data.get('channel_name')

    if channel_name != 'moderators':
        client.chat_postEphemeral(channel=channel_id, user=user_id, text="This is a mod command! Thanks for being a curious goose :)")
        return Response(), 200
    
    # gets the final vote and clears the vote dicts
    client.chat_postMessage(channel=channel_id, text=final_vote_to_str())
    vote_dict.clear()
    players_voted.clear()

    # updates the phase
    global phase
    current_phase = phase
    client.chat_postMessage(channel=channel_id, text="\nThe phase has changed from " + ("Day" if current_phase else "Night") + " to " + ("Day" if not current_phase else "Night"))
    phase = not phase

    print(data)
    return Response(), 200


# # Route for handling slash command requests
# @app.route("/slack/command", methods=["POST"])
# def command():
#     # Parse request body data
#     data = request.form

#     # Call the appropriate function based on the slash command
#     if data["command"] == "/joke":
#         message = get_joke()
#     else:
#         message = f"Invalid command: {data['command']}"

#     # Return response to Slack
#     return jsonify({"text": message})

# # Initialize SlackRequestHandler to handle requests from Slack
# handler = SlackRequestHandler(slack_app)

if __name__ == "__main__":
    # Start the Flask app on port 5000
    app.run(port=5000, debug=True)