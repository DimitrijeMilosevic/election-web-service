from flask import Flask, request, Response, jsonify
from configuration import Configuration
import re
from models import database, Participant, Election, ElectionParticipant, Vote
from email.utils import parseaddr
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, create_refresh_token, get_jwt, get_jwt_identity
from sqlalchemy import and_
from roleCheckDecorator import roleCheck
import datetime
import io
import csv
from time import strftime
from redis import Redis

application = Flask(__name__)
application.config.from_object(Configuration)

jwtManager = JWTManager(application)

@application.route('/vote', methods=['POST'])
@roleCheck('official')
def vote():
    if not ('file' in request.files):
        return jsonify(message='Field file is missing.'), 400

    accessClaims = get_jwt()
    electionOfficialJmbg = accessClaims['jmbg']

    content = request.files['file'].stream.read().decode('utf-8')
    stream = io.StringIO(content)
    reader = csv.reader(stream)

    votes = []
    rowNumber = 0
    for row in reader:
        if len(row) != 2:
            return jsonify(message=f'Incorrect number of values on line {rowNumber}.'), 400
        pollNumber = int(row[1])
        if pollNumber <= 0:
            return jsonify(message=f'Incorrect poll number on line {rowNumber}.'), 400
        voteObject = Vote(electionOfficialJmbg=electionOfficialJmbg, ballotGuid=row[0], pollNumber=pollNumber, reason=None, electionId=None)
        votes.append(voteObject)
        rowNumber = rowNumber + 1

    with Redis(Configuration.REDIS_HOST) as redis:
        redis.set(Configuration.REDIS_VOTES_ELECTIONOFFICIALJMBG_KEY, voteObject.electionOfficialJmbg)
        for voteObject in votes:
            redis.rpush(Configuration.REDIS_VOTES_BALLOTGUID_LIST, voteObject.ballotGuid)
            redis.rpush(Configuration.REDIS_VOTES_POLLNUMBER_LIST, voteObject.pollNumber)

    return Response(status=200)


if __name__ == '__main__':
    database.init_app(application)
    application.run(debug=True, host='0.0.0.0', port=5003)