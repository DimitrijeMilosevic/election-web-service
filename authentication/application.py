from flask import Flask, request, Response, jsonify
from configuration import Configuration
import re
from models import database, User, Role, UserRole
from email.utils import parseaddr
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, create_refresh_token, get_jwt, get_jwt_identity
from sqlalchemy import and_
from roleCheckDecorator import roleCheck

application = Flask(__name__)
application.config.from_object(Configuration)

def charToInt(c):
    return ord(c) - ord('0')

def getControlDigit(jmbg):

    controlDigit = 11 - ((7 * (charToInt(jmbg[0]) + charToInt(jmbg[6])) + 6 * (charToInt(jmbg[1]) + charToInt(jmbg[7]))
                            + 5 * (charToInt(jmbg[2]) + charToInt(jmbg[8])) + 4 * (charToInt(jmbg[3]) + charToInt(jmbg[9]))
                            + 3 * (charToInt(jmbg[4]) + charToInt(jmbg[10])) + 2 * (charToInt(jmbg[5]) + charToInt(jmbg[11]))) % 11)
    if controlDigit > 9:
        controlDigit = 0
    return controlDigit

JMBG_SIZE = 13
def isJMBGValid(jmbg):
    if len(jmbg) != JMBG_SIZE:
        return False
    jmbgRegex = '^((0\d)|([1-2]\d)|(3[0-1]))((0[1-9])|(1[0-2]))(\d{3})([7-9]\d)(\d{3})(\d)$'
    if not re.search(jmbgRegex, jmbg):
        return False
    return charToInt(jmbg[12]) == getControlDigit(jmbg)

def isEmailValid(email):
    if len(email) > 256:
        return False
    parseResult = parseaddr(email)
    return len(parseResult[1]) != 0

def isPasswordValid(password):
    if len(password) < 8:
        return False
    passwordRegex = '(?=.*[a-z])(?=.*[A-Z])(?=.*[\d]).*'
    if not re.search(passwordRegex, password):
        return False
    return True

@application.route('/register', methods=['POST'])
def register():
    jmbg = request.json.get('jmbg', '')
    forename = request.json.get('forename', '')
    surname = request.json.get('surname', '')
    email = request.json.get('email', '')
    password = request.json.get('password', '')

    jmbgEmpty = len(jmbg) == 0
    forenameEmpty = len(forename) == 0
    surnameEmpty = len(surname) == 0
    emailEmpty = len(email) == 0
    passwordEmpty = len(password) == 0

    if jmbgEmpty or forenameEmpty or surnameEmpty or emailEmpty or passwordEmpty:
        fieldName = ''
        if jmbgEmpty:
            fieldName = 'jmbg'
        elif forenameEmpty:
            fieldName = 'forename'
        elif surnameEmpty:
            fieldName = 'surname'
        elif emailEmpty:
            fieldName = 'email'
        elif passwordEmpty:
            fieldName = 'password'
        return jsonify(message=f'Field {fieldName} is missing.'), 400

    if not isJMBGValid(jmbg):
        return jsonify(message='Invalid jmbg.'), 400

    if not isEmailValid(email):
        return jsonify(message='Invalid email.'), 400

    if not isPasswordValid(password):
        return jsonify(message='Invalid password.'), 400

    user = User.query.filter(User.email == email).first()
    if user:
        return jsonify(message='Email already exists.'), 400

    user = User(email=email, password=password, forename=forename, surname=surname, jmbg=jmbg)
    database.session.add(user)
    database.session.commit()

    officialRole = Role.query.filter(Role.name == 'official').first()
    userRole = UserRole(userId=user.id, roleId=officialRole.id)
    database.session.add(userRole)
    database.session.commit()

    return Response(status=200)

jwtManager = JWTManager(application)

@application.route('/login', methods=['POST'])
def login():
    email = request.json.get('email', '')
    password = request.json.get('password', '')

    emailEmpty = len(email) == 0
    passwordEmpty = len(password) == 0

    if emailEmpty or passwordEmpty:
        fieldName = ''
        if emailEmpty:
            fieldName = 'email'
        elif passwordEmpty:
            fieldName = 'password'
        return jsonify(message=f'Field {fieldName} is missing.'), 400

    if not isEmailValid(email):
        return jsonify(message='Invalid email.'), 400

    user = User.query.filter(and_(User.email == email, User.password == password)).first()
    if not user:
        return jsonify(message='Invalid credentials.'), 400

    additionalClaims = {
        'jmbg': user.jmbg,
        'forename': user.forename,
        'surname': user.surname,
        'roles': [str(role) for role in user.roles]
    }
    accessToken = create_access_token(identity=user.email, additional_claims=additionalClaims)
    refreshToken = create_refresh_token(identity=user.email, additional_claims=additionalClaims)

    return jsonify(accessToken=accessToken, refreshToken=refreshToken)

@application.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    refreshClaims = get_jwt()

    additionalClaims = {
        'jmbg': refreshClaims['jmbg'],
        'forename': refreshClaims['forename'],
        'surname': refreshClaims['surname'],
        'roles': refreshClaims['roles']
    }
    accessToken = create_access_token(identity=identity, additional_claims=additionalClaims)

    return jsonify(accessToken=accessToken)

@application.route('/delete', methods=['POST'])
@roleCheck('admin')
def delete():
    email = request.json.get('email', '')
    emailEmpty = len(email) == 0
    if emailEmpty:
        return jsonify(message='Field email is missing.'), 400

    if not isEmailValid(email):
        return jsonify(message='Invalid email.'), 400

    user = User.query.filter(User.email == email).first()
    if not user:
        return jsonify(message='Unknown user.'), 400

    userRoles = UserRole.query.filter(UserRole.userId == user.id).all()
    for userRole in userRoles:
        database.session.delete(userRole)
        database.session.commit()

    database.session.delete(user)
    database.session.commit()
    return Response(status=200)

if __name__ == '__main__':
    database.init_app(application)
    application.run(debug=True, host='0.0.0.0', port=5001)

