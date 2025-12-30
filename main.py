import os
from flask import Flask, request, jsonify, Response
from slack_sdk import WebClient
from slack_sdk.web import SlackResponse
from slack_sdk.signature import SignatureVerifier

vote_dict = {}
players_voted = {}
phase = False  # True = Day, False = Night

# Initialize Flask app and Slack client
SIGNING_SECRET = os.environ["SIGNING_SECRET"]
SLACK_TOKEN = os.environ["SLACK_TOKEN"]

app = Flask(__name__)
client = WebClient(token=SLACK_TOKEN)
verifier = SignatureVerifier(SIGNING_SECRET)

BOT_ID = client.auth_test()['user_id']


def get_bot_channel():
    channels = client.conversations_list()['channels']
    for channel in channels:
        if channel['name'] == 'bot-commands':
            return channel['id']
    return None


# Route for Slack Events (URL verification + events)
@app.route("/slack/events", methods=["POST"])
def slack_events():
    if not verifier.is_valid_request(request.get_data(), request.headers):
        return "Request verification failed", 403

    data = request.get_json()
    if data.get("type") == "url_verification":
        return jsonify({"challenge": data["challenge"]}), 200

    # You can handle other events here if needed
    return Response(), 200


@app.route('/vote', methods=['POST'])
def vote():
    data = request.form
    user_id = data.get('user_id')
    user_name = data.get('user_name')
    text = data.get('text')
    channel_id = data.get('channel_id')
    channel_name = data.get('channel_name')

    if (phase and channel_name == 'main-chat') or (not phase and channel_name == 'koopa-troop'):
        player_vote(user_id, user_name, text, channel_id)
    elif channel_name == 'moderators':
        mod_vote(user_id, user_name, text, channel_id)
    else:
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=f"It's not the right time/place to use this command! You may only vote in #main-chat during the day, or in #koopa-troop during the night. Right now the phase is {'Day' if phase else 'Night'}."
        )
    return Response(), 200


def player_vote(user_id, user_name, text, channel_id):
    voted_before = players_voted.get(user_id, (None, None))[1]
    players_voted[user_id] = (user_name, text)

    vote_dict[text] = vote_dict.get(text, 0) + 1

    if voted_before:
        if vote_dict.get(voted_before) == 1:
            del vote_dict[voted_before]
        else:
            vote_dict[voted_before] -= 1
        action = "changed their vote to"
    else:
        action = "voted for"

    client.chat_postMessage(
        channel=channel_id,
        text=f"{user_name} {action} {text}, Current votes = {vote_dict[text]}"
    )
    bot_channel = get_bot_channel()
    if bot_channel:
        client.chat_postMessage(
            channel=bot_channel,
            text=f"{user_name} {action} {text}, Current votes = {vote_dict[text]}"
        )


def mod_vote(user_id, user_name, text, channel_id):
    vote_dict[text] = vote_dict.get(text, 0) + 1
    client.chat_postMessage(
        channel=channel_id,
        text=f"{user_name} voted for {text}, current votes = {vote_dict[text]}"
    )


def vote_count_to_str():
    sorted_dict = sorted(vote_dict.items(), key=lambda x: x[1], reverse=True)
    return "\n".join(f"{name}: {count}" for name, count in sorted_dict)


@app.route('/currentvotes', methods=['POST'])
def currentvotes():
    data = request.form
    user_id = data.get('user_id')
    channel_id = data.get('channel_id')
    channel_name = data.get('channel_name')

    if (phase and channel_name == 'main-chat') or (not phase and channel_name == 'koopa-troop') or channel_name == 'moderators':
        client.chat_postEphemeral(channel=channel_id, user=user_id, text=vote_count_to_str())
    else:
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text=f"It's not the right time/place to use this command! You may only view votes in #main-chat (day) or #koopa-troop (night). Phase is {'Day' if phase else 'Night'}."
        )
    return Response(), 200


@app.route('/endphase', methods=['POST'])
def endphase():
    data = request.form
    user_id = data.get('user_id')
    channel_id = data.get('channel_id')
    channel_name = data.get('channel_name')

    if channel_name != 'moderators':
        client.chat_postEphemeral(channel=channel_id, user=user_id, text="This is a mod command!")
        return Response(), 200

    # Post final votes
    sorted_votes = vote_count_to_str()
    client.chat_postMessage(channel=channel_id, text=f"The final votes are:\n{sorted_votes}")

    vote_dict.clear()
    players_voted.clear()

    global phase
    client.chat_postMessage(channel=channel_id, text=f"Phase changed from {'Day' if phase else 'Night'} to {'Day' if not phase else 'Night'}")
    phase = not phase

    return Response(), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
