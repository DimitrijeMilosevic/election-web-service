from flask import Flask, request, Response, jsonify
from configuration import Configuration
import re
from models import database, Participant, Election, ElectionParticipant, Vote
from email.utils import parseaddr
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, create_refresh_token, get_jwt, get_jwt_identity
from sqlalchemy import and_
from roleCheckDecorator import roleCheck
import datetime

application = Flask(__name__)
application.config.from_object(Configuration)

jwtManager = JWTManager(application)

@application.route('/createParticipant', methods=['POST'])
@roleCheck('admin')
def createParticipant():
    name = request.json.get('name', '')
    individual = request.json.get('individual', '')

    nameEmpty = len(name) == 0
    individualEmpty = (not isinstance(individual, bool))
    if nameEmpty or individualEmpty:
        fieldName = ''
        if nameEmpty:
            fieldName = 'name'
        elif individualEmpty:
            fieldName = 'individual'
        return jsonify(message=f'Field {fieldName} is missing.'), 400

    participant = Participant(name=name, individual=individual)
    database.session.add(participant)
    database.session.commit()

    return jsonify(id=participant.id)

@application.route('/getParticipants', methods=['GET'])
@roleCheck('admin')
def getParticipants():
    participants = Participant.query.all()
    participantsJSONArray = []
    for participant in participants:
        participantJSONObject = {
            'id': participant.id,
            'name': participant.name,
            'individual': participant.individual
        }
        participantsJSONArray.append(participantJSONObject)
    return jsonify(participants=participantsJSONArray)

ISO8601Format = '%Y-%m-%d %H:%M:%S'
def getDateInISO8601Format(date):
    try:
        datetimeObject = datetime.datetime.strptime(date, ISO8601Format)
    except ValueError:
        return None
    return datetimeObject

def electionsThen(startISO8601, endISO8601):
    elections = Election.query.all()
    for election in elections:
        electionStartISO8601 = getDateInISO8601Format(election.start)
        electionEndISO8601 = getDateInISO8601Format(election.end)
        if (startISO8601 < electionEndISO8601) and (electionStartISO8601 < endISO8601):
            return True
    return False


def areDatesValid(start, end):
    startISO8601 = getDateInISO8601Format(start)
    endISO8601 = getDateInISO8601Format(end)
    if (startISO8601 is None) or (endISO8601 is None):
        return False
    if startISO8601 >= endISO8601:
        return False
    return not electionsThen(startISO8601, endISO8601)

@application.route('/createElection', methods=['POST'])
@roleCheck('admin')
def createElection():
    start = request.json.get('start', '')
    end = request.json.get('end', '')
    individual = request.json.get('individual', '')
    participants = request.json.get('participants', '')

    startEmpty = len(start) == 0
    endEmpty = len(end) == 0
    individualEmpty = (not isinstance(individual, bool))
    participantsEmpty = (not isinstance(participants, list))

    if startEmpty or endEmpty or individualEmpty or participantsEmpty:
        fieldName = ''
        if startEmpty:
            fieldName = 'start'
        elif endEmpty:
            fieldName = 'end'
        elif individualEmpty:
            fieldName = 'individual'
        elif participantsEmpty:
            fieldName = 'participants'
        return jsonify(message=f'Field {fieldName} is missing.'), 400

    if not areDatesValid(start, end):
        return jsonify(message='Invalid date and time.')

    if len(participants) < 2:
        return jsonify(message='Invalid participant.')
    for participantId in participants:
        if not isinstance(participantId, int):
            return jsonify(message='Invalid participant.')
        participantObject = Participant.query.filter(Participant.id == participantId).first()
        if (not participantObject) or (participantObject.individual != individual):
            return jsonify(message='Invalid participant.')

    election = Election(start=start, end=end, individual=individual)
    database.session.add(election)
    database.session.commit()

    pollNumber = 1
    for participantId in participants:
        electionParticipant = ElectionParticipant(participantId=participantId, electionId=election.id, pollNumber=pollNumber)
        database.session.add(electionParticipant)
        database.session.commit()
        pollNumber = pollNumber + 1

    return jsonify(pollNumbers=list(range(1, len(participants) + 1)))

@application.route('/getElections', methods=['GET'])
@roleCheck('admin')
def getElections():
    elections = Election.query.all()
    electionsJSONArray = []
    for election in elections:
        participantsJSONArray = []
        for participant in election.participants:
            participantJSONObject = {
                'id': participant.id,
                'name': participant.name
            }
            participantsJSONArray.append(participantJSONObject)
        electionJSONObject = {
            'id': election.id,
            'start': election.start,
            'end': election.end,
            'individual': election.individual,
            'participants': participantsJSONArray
        }
        electionsJSONArray.append(electionJSONObject)
    return jsonify(elections=electionsJSONArray)

def isElectionOngoing(start, end):
    currentDatetimeISO8601 = datetime.datetime.strptime(datetime.datetime.now().strftime(ISO8601Format), ISO8601Format)
    startISO8601 = datetime.datetime.strptime(start, ISO8601Format)
    endISO8601 = datetime.datetime.strptime(end, ISO8601Format)
    return (currentDatetimeISO8601 > startISO8601) and (currentDatetimeISO8601 < endISO8601)

TOTAL_MANDATES = 250
THRESHOLD = 0.05
def dhont(totalVotes, totalNumberOfVotes):
    totalVotesWithCensus = {}
    for key, value in totalVotes.items():
        if (value / totalNumberOfVotes) > 0.05:
            totalVotesWithCensus[key] = value
        else:
            totalVotesWithCensus[key] = 0
    mandates = {}
    for key in totalVotesWithCensus:
        mandates[key] = 0
    while sum(mandates.values()) < TOTAL_MANDATES:
        maxVotes = max(totalVotesWithCensus.values())
        nextMandate = list(totalVotesWithCensus.keys())[list(totalVotesWithCensus.values()).index(maxVotes)]
        if nextMandate in mandates:
            mandates[nextMandate] = mandates[nextMandate] + 1
        else:
            mandates[nextMandate] = 1
        totalVotesWithCensus[nextMandate] = totalVotes[nextMandate] / (mandates[nextMandate] + 1)
    return mandates

@application.route('/getResults/<electionId>', methods=['GET'])
@roleCheck('admin')
def getResults(electionId):
    if not electionId:
        return jsonify(message='Field id is missing.'), 400
    election = Election.query.filter(Election.id == electionId).first()
    if not election:
        return jsonify(message='Election does not exist.'), 400
    if isElectionOngoing(election.start, election.end):
        return jsonify(message='Election is ongoing.'), 400

    validVotes = Vote.query.filter(Vote.reason.is_(None))
    totalVotes = {}
    for validVote in validVotes:
        pollNumber = validVote.pollNumber
        if pollNumber in totalVotes:
            totalVotes[pollNumber] = totalVotes[pollNumber] + 1
        else:
            totalVotes[pollNumber] = 1

    totalNumberOfVotes = 0
    participantsJSONArray = []
    for key, value in totalVotes.items():
        totalNumberOfVotes = totalNumberOfVotes + value
        participant = Participant.query.join(ElectionParticipant).filter(
            and_(ElectionParticipant.electionId == electionId, ElectionParticipant.pollNumber == key)).first()
        participantJSONObject = {
            'pollNumber': key,
            'name': participant.name,
            'result': value
        }
        participantsJSONArray.append(participantJSONObject)

    if election.individual:
        for participantJSONObject in participantsJSONArray:
            participantJSONObject['result'] = participantJSONObject['result'] / totalNumberOfVotes
    else:
        resultsDhont = dhont(totalVotes, totalNumberOfVotes)
        for key, value in resultsDhont.items():
            for participantJSONObject in participantsJSONArray:
                if participantJSONObject['pollNumber'] == key:
                    participantJSONObject['result'] = value

    invalidVotes = Vote.query.filter(Vote.reason.isnot(None))
    invalidVotesJSONArray = []
    for invalidVote in invalidVotes:
        invalidVoteJSONObject = {
            'electionOfficialJmbg': invalidVote.electionOfficialJmbg,
            'ballotGuid': invalidVote.ballotGuid,
            'pollNumber': invalidVote.pollNumber,
            'reason': invalidVote.reason
        }
        invalidVotesJSONArray.append(invalidVoteJSONObject)
    return jsonify(results=participantsJSONArray, invalidVotes=invalidVotesJSONArray), 200



if __name__ == '__main__':
    database.init_app(application)
    application.run(debug=True, host='0.0.0.0', port=5002)