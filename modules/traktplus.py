from flask import jsonify, render_template, request, json, send_file
import hashlib, urllib2, base64, random, time, datetime, os
from threading import Thread
from maraschino.tools import get_setting_value, requires_auth, create_dir, download_image
from maraschino import logger, app, WEBROOT, DATA_DIR, THREADS
from operator import itemgetter

TRAKT_TOKEN = {}
SYNC = {}
def trak_api(api, body={}, head={}, oauth=False ,dev=False):
    global TRAKT_TOKEN      
    url='https://api-v2launch.trakt.tv'
    username = get_setting_value('trakt_username')
            
    head.update({'Content-Type': 'application/json',
                  'trakt-api-version' : '2',
                  'trakt-api-key': 'f44a0396c599ac570a39434549882e648edee9c9ecb21827f246cbe309907584' #Trakt Client ID
                })
    
    if oauth and TRAKT_TOKEN:
        head.update({'trakt-user-token': TRAKT_TOKEN[username]})
        head.update({'trakt-user-login': username})
        
    if body:
        body = json.JSONEncoder().encode(body)
        request = urllib2.Request(url + api, data=body, headers=head)
    else:
        request = urllib2.Request(url + api, headers=head)
    
    response = urllib2.urlopen(request)
    response = response.read()
    response = json.JSONDecoder().decode(response)
    
    if dev:
      print url + api
      print head
      print body
      print json.dumps(response, sort_keys=True, indent=4)
    
    return response


def trakt_apitoken():
    global TRAKT_TOKEN, SYNC
    username = get_setting_value('trakt_username')

    if not username in TRAKT_TOKEN:
            password = get_setting_value('trakt_password')
            api = '/auth/login'

            credentials = {
                  'login': username,
                  'password': password
            }
            token = trak_api(api, body=credentials)
            TRAKT_TOKEN.update({username:token['token']})
            SYNC = read_sync()

def read_sync():
    username = get_setting_value('trakt_username')
    file_path = '%s/cache/trakt/sync.json' % DATA_DIR
    if os.path.isfile(file_path):
        data = open(file_path)
        data_string = data.read()
        data.close()
        json_data = json.JSONDecoder().decode(data_string)
        if not username in json_data:
            logger.log('TRAKT :: %s not found in %s' % (username, file_path), 'DEBUG')
            json_data = {username: {'watched': {'modified': '', 'trakt' : []},'collection': {'modified': '','trakt': []},'watchlist':{'modified':'','trakt':[]}}}
    else:
        logger.log('TRAKT :: file %s not found' % file_path, 'DEBUG')
        json_data = {username: {'watched': {'modified': '', 'trakt' : []},'collection': {'modified': '','trakt': []},'watchlist':{'modified':'','trakt':[]}}}

    return json_data

def update_sync(api_urls):
    global SYNC
    username = get_setting_value('trakt_username')
    file_path = '%s/cache/trakt/sync.json' % DATA_DIR

    print 'entering update_sync'
    print username, file_path

    for api in api_urls:
        key = api.split('/')[2]
        type = api.split('/')[3][:-1]
        try:
            response = trak_api(api, oauth=True)
        except Exception as e:
            trakt_exception(e)
            response = {}
        if response:
            if type == 'show':
                SYNC[username][key]['trakt'] = []
            for items in response:
                value = items[type]['ids']['trakt']
                SYNC[username][key]['trakt'].append(value)

    try:
        with open(file_path, 'w') as outfile:
            json.dump(SYNC, outfile)
    except Exception as e:
        print e
    outfile.close


def sync_url():
    global SYNC
    username = get_setting_value('trakt_username')
    api = '/sync/last_activities'
    api_urls=[]

    try:
        response = trak_api(api, oauth=True, dev=True)
    except Exception as e:
        print e
        sleep(10)
        try:
            response = trak_api(api, oauth=True)
        except Exception as e:
            print e
            return False

    if not SYNC[username]['watched']['modified']:
        SYNC[username]['watched']['modified'] = '1950-01-01T00:00:00.000Z'
    lastupdate = datetime.datetime.strptime( SYNC[username]['watched']['modified'], "%Y-%m-%dT%H:%M:%S.%fZ" )
    currentmovie = datetime.datetime.strptime( response['movies']['watched_at'], "%Y-%m-%dT%H:%M:%S.%fZ" )
    currentshow = datetime.datetime.strptime( response['episodes']['watched_at'], "%Y-%m-%dT%H:%M:%S.%fZ" )

    if lastupdate < currentmovie or lastupdate < currentshow:
        api_urls.append('/sync/watched/shows')
        api_urls.append('/sync/watched/movies')
        if currentmovie < currentshow:
            SYNC[username]['watched']['modified'] = currentshow.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        else:
            SYNC[username]['watched']['modified'] = currentmovie.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    if not SYNC[username]['collection']['modified']:
        SYNC[username]['collection']['modified'] = '1950-01-01T00:00:00.000Z'
    lastupdate = datetime.datetime.strptime( SYNC[username]['collection']['modified'], "%Y-%m-%dT%H:%M:%S.%fZ" )
    currentmovie = datetime.datetime.strptime( response['movies']['collected_at'], "%Y-%m-%dT%H:%M:%S.%fZ" )
    currentshow = datetime.datetime.strptime( response['episodes']['collected_at'], "%Y-%m-%dT%H:%M:%S.%fZ" )

    if lastupdate < currentmovie or lastupdate < currentshow:
        api_urls.append('/sync/collection/shows')
        api_urls.append('/sync/collection/movies')
        if currentmovie < currentshow:
            SYNC[username]['collection']['modified'] = currentshow.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        else:
            SYNC[username]['collection']['modified'] = currentmovie.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    if not SYNC[username]['watchlist']['modified']:
        SYNC[username]['watchlist']['modified'] = '1950-01-01T00:00:00.000Z'
    lastupdate = datetime.datetime.strptime( SYNC[username]['watchlist']['modified'], "%Y-%m-%dT%H:%M:%S.%fZ" )
    currentmovie = datetime.datetime.strptime( response['movies']['watchlisted_at'], "%Y-%m-%dT%H:%M:%S.%fZ" )
    currentshow = datetime.datetime.strptime( response['episodes']['watchlisted_at'], "%Y-%m-%dT%H:%M:%S.%fZ" )

    if lastupdate < currentmovie or lastupdate < currentshow:
        api_urls.append('/sync/watchlist/shows')
        api_urls.append('/sync/watchlist/movies')
        if currentmovie < currentshow:
            SYNC[username]['watchlist']['modified'] = currentshow.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        else:
            SYNC[username]['watchlist']['modified'] = currentmovie.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            
    return api_urls

def trakt_exception(e):
    logger.log('TRAKT :: EXCEPTION -- %s' % e, 'DEBUG')
    return e

def get_list(content, media_type):
    if content == 'lists':
          api = '/users/me/lists'
    else:
          api = '/sync/%s/%s' % (content, media_type)
    list = trak_api(api, oauth=True)
    
    return list

create_dir(os.path.join(DATA_DIR, 'cache', 'trakt', 'shows'))
create_dir(os.path.join(DATA_DIR, 'cache', 'trakt', 'movies'))

def small_poster(image):
    if not 'poster-small' in image:
        x = image.rfind('.')
        #image = image[:x] + '-138' + image[x:]
    return image


def cache_image(image, type):
    if type == 'shows':
        dir = '%s/cache/trakt/shows' % DATA_DIR
    else:
        dir = '%s/cache/trakt/movies' % DATA_DIR

    image = small_poster(image)

    x = image.rfind('/')
    filename = image[x:]
    filename = filename.split("?")[0]
    file_path = "%s%s" % (dir, filename)

    if not os.path.exists(file_path):
        Thread(target=download_image, args=(image, file_path)).start()
        THREADS.append(len(THREADS) + 1)

    return '%s/cache/trakt/%s/%s' % (WEBROOT, type, filename[1:])

@app.template_filter('format_date')
def format_date(value, format='date'):
    if format == 'date':
        return datetime.datetime.strptime(value[:10], '%Y-%m-%d').strftime('%B %d, %Y')
    if format == 'day':
        return datetime.datetime.strptime(value[:10], '%Y-%m-%d').strftime('%A, %B %d, %Y')
    if format == 'time':
        return datetime.datetime.strptime(value, '%H:%M').strftime('%I:%M %p').lstrip('0')
    if format == 'datetime':
        return datetime.datetime.strptime(value[:23], '%Y-%m-%dT%H:%M:%S.%f').strftime('%A, %B %d at %I:%M %p')

@app.route('/cache/trakt/<type>/<filename>')
@requires_auth
def img_cache(type, filename):
    img = os.path.join(DATA_DIR, 'cache', 'trakt', type, filename)
    return send_file(img, mimetype='image/jpeg')


@app.route('/xhr/traktplus/')
def xhr_traktplus():
    default = get_setting_value('trakt_default_view')

    if default == 'trending_shows':
        return xhr_trakt_trending('shows')
    elif default == 'trending_movies':
        return xhr_trakt_trending('movies')
    elif default == 'activity_friends':
        return xhr_trakt_activity('friends')
    elif default == 'activity_community':
        return xhr_trakt_activity('community')
    elif default == 'friends':
        return xhr_trakt_friends()
    elif default == 'calendar':
        return xhr_trakt_calendar('my shows')
    elif default == 'recommendations_shows':
        return xhr_trakt_recommendations('shows')
    elif default == 'recommendations_movies':
        return xhr_trakt_recommendations('movies')
    elif default == 'profile':
        return xhr_trakt_profile()


@app.route('/xhr/trakt/recommendations')
@app.route('/xhr/trakt/recommendations/<type>')
def xhr_trakt_recommendations(type=None, mobile=False):
    if not type:
        type = get_setting_value('trakt_default_media')

    logger.log('TRAKT :: Fetching %s recommendations' % type, 'INFO')

    api = '/recommendations/%s?extended=full,images' % (type)

    try:
        recommendations = trak_api(api, oauth=True)
    except Exception as e:
        trakt_exception(e)
        return render_template('traktplus/trakt-base.html', message=e)

    random.shuffle(recommendations)

    for item in recommendations:
        if item['images']['poster']['thumb']:
            item['images']['poster']['thumb'] = cache_image(item['images']['poster']['thumb'], type)

    while THREADS:
        time.sleep(1)

    if mobile:
        return recommendations

    return render_template('traktplus/trakt-recommendations.html',
        type=type.title(),
        recommendations=recommendations,
        title='Recommendations',
    )


@app.route('/xhr/trakt/trending')
@app.route('/xhr/trakt/trending/<type>')
@requires_auth
def xhr_trakt_trending(type=None, mobile=False):
    username = get_setting_value('trakt_username')
    
    if not type:
        type = get_setting_value('trakt_default_media')

    trakt_apitoken()
    api_urls = sync_url()
    if api_urls:
        update_sync(api_urls)
    
    limit = int(get_setting_value('trakt_trending_limit'))
    logger.log('TRAKT :: Fetching trending %s' % type, 'INFO')

    api = '/%s/trending?extended=full,images&page=1&limit=%s' % (type, limit)
    
    try:
        trakt = trak_api(api)
    except Exception as e:
        trakt_exception(e)
        return render_template('traktplus/trakt-base.html', message=e)
    
    if mobile:
        return trakt

    if type == 'shows':
          for item in trakt:
                item['show']['images']['poster']['thumb'] = cache_image(item['show']['images']['poster']['thumb'], type)
                item['show']['rating'] = int(item['show']['rating'] * 10)
                for ids in SYNC[username]['watched']['trakt']:
                    if ids == item['show']['ids']['trakt']:
                        item['show'].update({'watched':True})
                        break
                for ids in SYNC[username]['collection']['trakt']:
                    if ids == item['show']['ids']['trakt']:
                        item['show'].update({'in_collection':True})
                        break
                for ids in SYNC[username]['watchlist']['trakt']:
                    if ids == item['show']['ids']['trakt']:
                        item['show'].update({'in_watchlist':True})
                        break
    else:
          for item in trakt:
                item['movie']['images']['poster']['thumb'] = cache_image(item['movie']['images']['poster']['thumb'], type)
                item['movie']['rating'] = int(item['movie']['rating'] * 10)
                for ids in SYNC[username]['watched']['trakt']:
                    if ids == item['movie']['ids']['trakt']:
                        print 'matched', item['movie']['ids']['slug']
                        item['movie'].update({'watched':True})
                        break
                for ids in SYNC[username]['collection']['trakt']:
                    if ids == item['movie']['ids']['trakt']:
                        print 'matched', item['movie']['ids']['slug']
                        item['movie'].update({'watched':True})
                        break
                for ids in SYNC[username]['watchlist']['trakt']:
                    if ids == item['movie']['ids']['trakt']:
                        print 'matched', item['movie']['ids']['slug']
                        item['movie'].update({'in_watchlist':True})
                        break
    while THREADS:
        time.sleep(1)

    return render_template('traktplus/trakt-trending.html',
        trending=trakt,
        type=type.title(),
        title='Trending',
    )

@app.route('/xhr/trakt/activity')
@app.route('/xhr/trakt/activity/<type>')
@requires_auth
def xhr_trakt_activity(type='friends', mobile=False):
    logger.log('TRAKT :: Fetching %s activity' % type, 'INFO')

    url = 'http://api.trakt.tv/activity/%s.json/%s' % (type, trakt_apikey())
    try:
        trakt = trak_api(url)
    except Exception as e:
        trakt_exception(e)
        return render_template('traktplus/trakt-base.html', message=e)

    if mobile:
        return trakt

    return render_template('traktplus/trakt-activity.html',
        activity=trakt,
        type=type.title(),
        title='Activity',
    )

@app.route('/xhr/trakt/friends')
@app.route('/xhr/trakt/friends/<user>')
@requires_auth
def xhr_trakt_friends(user=None, mobile=False):
    logger.log('TRAKT :: Fetching friends list', 'INFO')
    pending = None
    responses = []
    
    if not user:
        friends_api = '/users/me/friends?extended=full,images'
        pending_api = '/users/requests'
    else:
        friends_api = '/users/%s/friends?extended=full,images' % (user)

    try:
        friends = trak_api(friends_api, oauth=True)
        if not user:
            pending = trak_api(pending_api, oauth=True)
    except Exception as e:
        trakt_exception(e)
        return render_template('traktplus/trakt-base.html', message=e)
    
    for friend in friends:
        api = ['/users/%s/history/movies' % friend['user']['username'],
               '/users/%s/history/episodes' % friend['user']['username'],
               '/users/%s/watching' % friend['user']['username'] ]
        for url in api:
            try:
                response = trak_api(url, oauth=True)
            except Exception as e:
                trakt_exception(e)
                response = None
            responses.append(response)
            
        if responses[0] and responses[1]:
            history = sorted(responses[0] + responses[1], key=itemgetter('watched_at'), reverse=True)
        else:
            if responses[0]:
                history = responses[0]
            elif responses[1]:
                history = responses[1]
            else:
                history = None
        if history:
            friend.update({'watched':history[:1]})
        if responses[2]:
            friend.update({'watching':responses[2]})

        responses = []
    
    if mobile:
        return friends

    return render_template('traktplus/trakt-friends.html',
        friends=friends,
        pending=pending,
        title='Friends',
    )


@app.route('/xhr/trakt/friend/<action>/<user>')
@requires_auth
def xhr_trakt_friend_action(action, user):
    api = '/users/%s/history/%s' % (action, user)
    
    header = {
        'trakt-user-login': '%s' % (get_setting_value('trakt_username')),
    }
    
    try:
        trakt = trak_api(api, {}, header, True, True)
    except Exception as e:
        trakt_exception(e)
        return jsonify(status='%s friend failed\n%s' % (action.title(), e))

    if trakt['status'] == 'success':
        return jsonify(status='successful')
    else:
        return jsonify(status=action.title() + ' friend failed')


@app.route('/xhr/trakt/profile')
@app.route('/xhr/trakt/profile/<user>')
@requires_auth
def xhr_trakt_profile(user=None, mobile=False):
    if not user:
        user = 'me'
        username = get_setting_value('trakt_username')
    else:
        username = user

    logger.log('TRAKT :: Fetching %s\'s profile information' % user, 'INFO')
    counts = {'collected_e': 0, 'collected_w': 0, 'watched_m': 0, 'total_m': 0, 'watched_e': 0, 'total_e': 0} 
    api_urls = ['/users/%s?extended=full,images' % (user), '/users/%s/history/movies?extended=full,images&page=1&limit=5' % (user),
                '/users/%s/history/episodes?extended=full,images&page=1&limit=5' % (user), '/users/%s/watching' % (user) ,
                '/sync/collection/movies', '/sync/collection/shows', '/sync/watched/shows']
    responses = []
    for url in api_urls:
        try:
            response = trak_api(url, oauth=True)
        except Exception as e:
            trakt_exception(e)
        
        responses.append(response)
        response = None
    
    for collection in responses[5]:
        for s in collection['seasons']:
            counts['total_e'] += len(s['episodes'])
        for watch in responses[6]:
            if watch['show']['ids']['trakt'] == collection['show']['ids']['trakt']:
                for s in collection['seasons']:
                    counts['collected_e'] += len(s['episodes'])
                for s in watch['seasons']:
                    counts['collected_w'] += len(s['episodes'])
                if counts['collected_e'] > counts['collected_w']:
                    counts['watched_e'] += counts['collected_w']
                else:
                    counts['watched_e'] += counts['collected_e']
                counts['collected_e'] = 0
                counts['collected_w'] = 0
    
    counts['total_m'] = len(responses[4])
    
    for collection in responses[4]:
        for id in SYNC[username]['watched']['trakt']:
            if id == collection['movie']['ids']['trakt']:
                counts['watched_m'] += 1
                break

    try:
        movies_progress = 100 * float(counts['watched_m']) / float(counts['total_m'])
    except Exception as e:
       print e
       movies_progress = 0
    try:
       episodes_progress = 100 * float(counts['watched_e']) / float(counts['total_e'])
    except Exception as e:
       print e
       episodes_progress = 0

    try:
        history = sorted(responses[1] + responses[2][:5], key=itemgetter('watched_at'), reverse=True)
    except Exception as e:
        print 'Exception', e


    if mobile:
        return trakt

    return render_template('traktplus/trakt-user_profile.html',
        history=history,
        scrobble=responses[3],
        profile=responses[0],
        user=user,
        movies_progress=int(movies_progress),
        episodes_progress=int(episodes_progress),
        stats=counts,
        title='Profile',
    )


@app.route('/xhr/trakt/progress/<user>')
@app.route('/xhr/trakt/progress/<user>/<type>')
@requires_auth
def xhr_trakt_progress(user, type=None, mobile=False):
    if not type:
        type = 'watched'

    logger.log('TRAKT :: Fetching %s\'s %s progress' % (user, type), 'INFO')
    url = 'http://api.trakt.tv/user/progress/%s.json/%s/%s' % (type, trakt_apikey(), user)

    try:
        trakt = trak_api(url)
    except Exception as e:
        trakt_exception(e)
        return render_template('traktplus/trakt-base.html', message=e)

    if mobile:
        return trakt

    return render_template('traktplus/trakt-progress.html',
        progress=trakt,
        user=user,
        type=type,
    )


@app.route('/xhr/trakt/library/<user>')
@app.route('/xhr/trakt/library/<user>/<type>')
@requires_auth
def xhr_trakt_library(user, type=None, mobile=False):
    if not type:
        type = get_setting_value('trakt_default_media')

    logger.log('TRAKT :: Fetching %s\'s %s library' % (user, type), 'INFO')
    api = '/users/%s/collection/%s' % (user, type)

    header = {
        'trakt-user-login': '%s' % (get_setting_value('trakt_username')),
    }
    
    try:
        trakt = trak_api(api, {}, header, True, True)
    except Exception as e:
        trakt_exception(e)
        return render_template('traktplus/trakt-base.html', message=e)

    if mobile:
        return trakt

    return render_template('traktplus/trakt-library.html',
        library=trakt,
        user=user,
        type=type.title(),
        title='Library',
    )


@app.route('/xhr/trakt/watchlist/<user>')
@app.route('/xhr/trakt/watchlist/<user>/<type>')
@requires_auth
def xhr_trakt_watchlist(user, type=None, mobile=False):
    if not type:
        type = get_setting_value('trakt_default_media')

    logger.log('TRAKT :: Fetching %s\'s %s watchlist' % (user, type), 'INFO')
    api = '/users/%s/watchlist/%s' % (user, type)
    
    header = {
        'trakt-user-login': '%s' % (get_setting_value('trakt_username')),
    }

    try:
        trakt = trak_api(api, {}, header, True, True)
    except Exception as e:
        trakt_exception(e)
        return render_template('traktplus/trakt-base.html', message=e)

    if mobile:
        return trakt

    if trakt == []:
        trakt = [{'empty': True}]

    return render_template('traktplus/trakt-watchlist.html',
        watchlist=trakt,
        type=type.title(),
        user=user,
        title='Watchlist',
    )


@app.route('/xhr/trakt/rated/<user>/<type>')
@app.route('/xhr/trakt/rated/<user>')
@requires_auth
def xhr_trakt_rated(user, type=None, mobile=False):
    if not type:
        type = get_setting_value('trakt_default_media')
    logger.log('TRAKT :: Fetching %s\'s rated %s' % (user, type), 'INFO')
    api = '/users/%s/ratings/%s' % (user, type)
    
    header = {
        'trakt-user-login': '%s' % (get_setting_value('trakt_username')),
    }
    
    try:
        trakt = trak_api(api, {}, header, True, True)
    except Exception as e:
        trakt_exception(e)
        return render_template('traktplus/trakt-base.html', message=e)

    if mobile:
        return trakt

    total = len(trakt)
    loved = 0
    hated = 0
    rated = {
        'loved': [],
        'hated': []
    }

    if trakt:
        for item in trakt:
            if item['rating'] == 'love':
                rated['loved'].append(item)
            elif item['rating'] == 'hate':
                rated['hated'].append(item)
        loved = len(rated['loved'])
        hated = len(rated['hated'])

    return render_template('traktplus/trakt-rated.html',
        rated=rated,
        total=total,
        loved=loved,
        hated=hated,
        type=type.title(),
        user=user,
        title='Rated',
    )


@app.route('/xhr/trakt/calendar/<type>')
@requires_auth
def xhr_trakt_calendar(type, mobile=False):
    logger.log('TRAKT :: Fetching %s calendar' % type, 'INFO')
    today = time.strftime('%Y-%m-%d')

    if type != 'Premieres':
        api = '/calendars/shows/%s/6?extended=full' % today
        auth = False
    if type == 'my shows':
        auth = True
    else:
        api = '/calendars/shows/premieres/%s/6?extended=full' % today
        auth = False

    try:
        trakt = trak_api(api, {}, oauth=auth)
    except Exception as e:
        trakt_exception(e)
        return render_template('traktplus/trakt-base.html', message=e)

    dates = trakt.keys()
    dates.sort()
    if mobile:
        return trakt

    return render_template('traktplus/trakt-calendar.html',
        calendar=trakt,
        dates=dates,
        type=type.title(),
        title='Calendar',
    )


@app.route('/xhr/trakt/summary/<type>/<id>')
@app.route('/xhr/trakt/summary/<type>/<id>/<season>/<episode>')
@requires_auth
def xhr_trakt_summary(type, id, season=None, episode=None, mobile=False):
    username = get_setting_value('trakt_username')
    api_urls = sync_url()
    if api_urls:
        update_sync(api_urls)

    if type == 'episode':
        api = '/show/%s/seasons/%s/episodes/%s?extended=full,images' % (id, season, episode)
        stat_api = '/show/%s/seasons/%s/episodes/%s/stats' % (id, season, episode)
    elif type == 'show':
        api = '/shows/%s?extended=full,images' % (id)
        stat_api = '/shows/%s/stats' % (id)
    else:
        api = '/movies/%s?extended=full,images' % (id)
        stat_api = '/movies/%s/stats' % (id)

    try:
        trakt = trak_api(api, oauth=True)
    except Exception as e:
        trakt_exception(e)
        return render_template('traktplus/trakt-base.html', message=e)
    
    try:
        trakt_stat = trak_api(stat_api, oauth=True)
    except Exception as e:
        trakt_exception(e)
        return render_template('traktplus/trakt-base.html', message=e)
        
    if type != 'episode':
        trakt['images']['poster']['thumb'] = cache_image(trakt['images']['poster']['thumb'], type + 's')
        trakt['rating'] = trakt['rating'] * 10
        for ids in SYNC[username]['watched']['trakt']:
            if ids == trakt['ids']['trakt']:
               trakt.update({'watched': True})
        for ids in SYNC[username]['collection']['trakt']:
            if ids == trakt['ids']['trakt']:
               trakt.update({'in_collection': True})
        for ids in SYNC[username]['watchlist']['trakt']:
            if ids == trakt['ids']['trakt']:
               trakt.update({'in_watchlist': True})

        if type == 'show' or type == 'episode':
            trakt['first_aired'] = datetime.datetime.strptime( trakt['first_aired'], "%Y-%m-%dT%H:%M:%S.000Z" ).strftime('%B %d, %Y')
            trakt['airs']['time'] = datetime.datetime.strptime(trakt['airs']['time'], '%H:%M').time().strftime('%I:%M %p')

    while THREADS:
        time.sleep(1)

    if mobile:
        return trakt

    if type == 'episode':
        return render_template('traktplus/trakt-episode.html',
            episode=trakt,
            type=type,
            title=trakt['episode']['title'],
            stats=trakt_stat,
            )
    elif type == 'show':
        return render_template('traktplus/trakt-show.html',
            show=trakt,
            type=type,
            title=trakt['title'],
            stats=trakt_stat,
            )
    else:
        return render_template('traktplus/trakt-movie.html',
            movie=trakt,
            type=type,
            title=trakt['title'],
            stats=trakt_stat,
            )


@app.route('/xhr/trakt/get_lists/', methods=['POST'])
@app.route('/xhr/trakt/get_lists/<user>', methods=['GET'])
@requires_auth
def xhr_trakt_get_lists(user=None, mobile=False):
    if not user:
        user = get_setting_value('trakt_username')

    logger.log('TRAKT :: Fetching %s\'s custom lists' % user, 'INFO')
    api = '/user/%s/lists' % (user)
    
    header = {
        'trakt-user-login': '%s' % (get_setting_value('trakt_username')),
    }

    try:
        trakt = trak_api(api, {}, header, True, True)
    except Exception as e:
        trakt_exception(e)
        return render_template('traktplus/trakt-base.html', message=e)

    if request.method == 'GET':
        if mobile:
            return trakt

        return render_template('traktplus/trakt-custom_lists.html',
            lists=trakt,
            user=user,
            title='lists'
        )

    else:
        return render_template('traktplus/trakt-add_to_list.html',
            lists=trakt,
            custom_lists=True,
            media=request.form,
        )


@app.route('/xhr/trakt/list/<slug>/<user>')
@requires_auth
def xhr_trakt_custom_list(slug, user, mobile=False):

    logger.log('TRAKT :: Fetching %s' % slug, 'INFO')
    api = '/users/%s/lists/%s/items?extended=full,images' % (user, slug)

    try:
        trakt = trak_api(url)
    except Exception as e:
        trakt_exception(e)
        return render_template('traktplus/trakt-base.html', message=e)

    if mobile:
        return trakt

    return render_template('traktplus/trakt-custom_lists.html',
        list=trakt,
        title=trakt['name'],
    )


@app.route('/xhr/trakt/add_to_list/', methods=['POST'])
@requires_auth
def xhr_trakt_add_to_list():
    media = json.JSONDecoder().decode(request.form['media'])
    list = json.JSONDecoder().decode(request.form['list'])
    exist = request.form['exist']

    if exist == 'false':
        logger.log('TRAKT :: Creating new custom list: %s' % (list[0]['value']), 'INFO')
        
        api = '/users/%s/lists' % (get_setting_value('trakt_username'))
        
        header = {
        'trakt-user-login': '%s' % (get_setting_value('trakt_username')),
        }
        
        list_params = {}
        for item in list:
            if item['value'] == '0':
                item['value'] = False
            elif item['value'] == '1':
                item['value'] == True
            list_params[item['name']] = item['value']

        list = list_params

        try:
            trakt = trak_api(api, list, header, True, True)
        except Exception as e:
            trakt_exception(e)
            return jsonify(status='Failed to add %s to %s\n%s' % (media['title'], list['name'], e))

        list['slug'] = list['name'].replace(' ', '-')

    logger.log('TRAKT :: Adding %s to %s' % (media['title'], list['name']), 'INFO')
    api = '/users/%s/lists/%s' % (get_setting_value('trakt_username'), list['slug'] )
    params = {
        'slug': list['slug'],
        'items': [media]
    }
    
    header = {
        'trakt-user-login': '%s' % (get_setting_value('trakt_username')),
    }
    
    try:
        trakt = trak_api(api, params, header, True, True)
    except Exception as e:
        trakt_exception(e)
        return jsonify(status='Failed to add %s to %s\n%s' % (media['title'], list['name'], e))

    if trakt['status'] == 'success':
        return jsonify(status='successful')
    else:
        return jsonify(status='Failed to add %s to %s' % (media['title'], list['name']))


@app.route('/xhr/trakt/action/<action>/<type>/', methods=['POST'])
@requires_auth
def xhr_trakt_action(type, action):
    #rate, seen, watchlist, library, dismiss
    logger.log('TRAKT :: %s: %s' % (type, action), 'INFO')
    url = 'http://api.trakt.tv/%s/%s/%s' % (type, action, trakt_apikey())
    params = {}

    if action == 'rate':
        url = 'http://api.trakt.tv/rate/%s/%s' % (type, trakt_apikey())
        for k, v in request.form.iteritems():
            params[k] = v

    if action == 'library' and type == 'show':
        for k, v in request.form.iteritems():
            params[k] = v

    elif action == 'dismiss':
        url = 'http://api.trakt.tv/recommendations/%ss/dismiss/%s' % (type, trakt_apikey())
        for k, v in request.form.iteritems():
            params[k] = v

    else:
        params[type + 's'] = [{}]

        for k, v in request.form.iteritems():
            params[type + 's'][0][k] = v

    if action == 'seen':
        params[type + 's'][0]['plays'] = 1
        params[type + 's'][0]['last_played'] = int(time.time())

    try:
        trakt = trak_api(url, params)
    except Exception as e:
        trakt_exception(e)
        return jsonify(status='Action failed\n%s' % e)

    if trakt['status'] == 'success':
        return jsonify(status='successful')
    else:
        return jsonify(status='Action failed')
