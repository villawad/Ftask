# Ftask, simple TODO list application
# Copyright (C) 2012 Daniel Garcia <danigm@wadobo.com>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import division, absolute_import

from flask import Blueprint
from flask import abort
from flask import jsonify
from flask import request
from flask import session
from flask import g
from ..db import get_db, to_json
from .apikey import new_user_apikey, user_by_apikey, delete_apikey
from .decorators import authenticated

from hashlib import sha256
import string
import random
import datetime


auth = Blueprint('auth', __name__, template_folder='templates')

def generate_csrf_token():
    if '_csrf_token' not in session:
        choices = string.ascii_letters + string.digits
        token = ''.join(random.choice(choices) for x in range(20))
        session['_csrf_token'] = token

    return session['_csrf_token']


def csrf_token():
    return '<input name="_csrf_token" id="csrf_token" type="hidden" value="%s">' % generate_csrf_token()


def auth_before_request():
    g.user = None
    g.apikey = None

    if 'apikey' in request.headers:
        g.user = user_by_apikey(request.headers['apikey'])
        g.apikey = request.headers['apikey']
        return

    if 'user_id' in session:
        g.user = get_db().users.find_one({'username': session['user_id']})

        # checking csrf
        if request.method in ["POST", "PUT", "DELETE"]:
            token = session.pop('_csrf_token', None)
            if not token or token != request.values.get('_csrf_token'):
                abort(403)


@auth.route('/')
def list_users():
    users = get_db().users.find()
    meta = {}
    meta['total'] = users.count()
    objs = [to_json(i, excludes=['password']) for i in users]

    return jsonify(meta=meta,
                   objects=objs)


@auth.route('/find/')
def find_users():
    q = request.args.get('q', '')
    users = get_db().users.find({'$or': [{'username': {'$regex': q}}, {'email': {'$regex': q}}]})
    meta = {}
    meta['total'] = users.count()
    objs = [to_json(i, excludes=['password']) for i in users]

    return jsonify(meta=meta,
                   objects=objs)


@auth.route('/register/', methods=['POST'])
def register():
    c = get_db().users
    username = request.form['username']
    pw = sha256(request.form['password']).hexdigest()
    email = request.form['email']

    u = {'username': username,
         'password': pw,
         'email': email}

    if c.find({"username": username}).count():
        raise abort(400)

    c.insert(u)

    return jsonify(status="success")


@auth.route('/login/', methods=['POST'])
def login():
    db = get_db()
    c = db.users
    username = request.form['username']
    pw = sha256(request.form['password']).hexdigest()

    if c.find({"username": username}).count() == 0:
        raise abort(400)

    u = c.find_one({"username": username})
    if u['password'] != pw:
        raise abort(400)

    session['user_id'] = username
    apikey = new_user_apikey(u)

    resp = jsonify(status="success")
    resp.headers['Authorization'] = apikey['key']
    return resp


@auth.route('/logout/', methods=['POST'])
def logout():
    if g.user:
        del session['user_id']
        g.user = None
    if g.apikey:
        delete_apikey(g.apikey)
        g.apikey = None

    return jsonify(status="success")


@auth.route('/profile/', methods=['GET', 'POST'])
@authenticated
def profile():
    return jsonify(to_json(g.user, excludes=['password']))


@auth.route('/csrf_token/')
@authenticated
def csrf_token_view():
    return jsonify(token=generate_csrf_token())
