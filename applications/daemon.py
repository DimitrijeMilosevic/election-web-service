from configuration import Configuration
from models import database, Election, Vote, ElectionParticipant
import datetime
from redis import Redis
from sqlalchemy import and_
from flask import Flask

application = Flask(__name__)
application.config.from_object(Configuration)

ISO8601Format = '%Y-%m-%d %H:%M:%S'
def getCurrentElectionId():
    currentDatetimeISO8601 = datetime.datetime.strptime(datetime.datetime.now().strftime(ISO8601Format), ISO8601Format)
    elections = Election.query.all()
    for election in elections:
        startISO8601 = datetime.datetime.strptime(election.start, ISO8601Format)
        endISO8601 = datetime.datetime.strptime(election.end, ISO8601Format)
        if (currentDatetimeISO8601 > startISO8601) and (currentDatetimeISO8601 < endISO8601):
            return election.id
    return -1

if __name__ == '__main__':
    database.init_app(application)
    with application.app_context():
        while True:
            with Redis(Configuration.REDIS_HOST) as redis:
                ballotGuidBytes = redis.blpop(Configuration.REDIS_VOTES_BALLOTGUID_LIST, 0)[1]
                ballotGuid = ballotGuidBytes.decode('utf-8')
                pollNumberBytes = redis.lpop(Configuration.REDIS_VOTES_POLLNUMBER_LIST)
                pollNumber = pollNumberBytes.decode('utf-8')
                currentElectionId = getCurrentElectionId()
                if currentElectionId != -1:
                    electionOfficialJmbg = redis.get(Configuration.REDIS_VOTES_ELECTIONOFFICIALJMBG_KEY)
                    reason = None
                    voteWithBallotGUID = Vote.query.filter(Vote.ballotGuid == ballotGuid).first()
                    if voteWithBallotGUID:
                        reason = 'Duplicate ballot.'
                    participantWithPollNumber = ElectionParticipant.query.filter(
                        and_(ElectionParticipant.electionId == currentElectionId,
                             ElectionParticipant.pollNumber == pollNumber)).first()
                    if not participantWithPollNumber:
                        reason = 'Invalid poll number.'
                    vote = Vote(electionOfficialJmbg=electionOfficialJmbg, ballotGuid=ballotGuid, pollNumber=pollNumber,
                                reason=reason, electionId=currentElectionId)
                    database.session.add(vote)
                    database.session.commit()
