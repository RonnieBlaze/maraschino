from flask import jsonify, render_template, request, send_file, json
import urllib2
import base64
import StringIO

from maraschino import app, logger, WEBROOT
from maraschino.tools import *
import maraschino


def sickrage_http():
    if get_setting_value('sickrage_https') == '1':
        return 'https://'
    else:
        return 'http://'


def sickrage_url():
    port = get_setting_value('sickrage_port')
    url_base = get_setting_value('sickrage_ip')
    webroot = get_setting_value('sickrage_webroot')

    if port:
        url_base = '%s:%s' % (url_base, port)

    if webroot:
        url_base = '%s/%s' % (url_base, webroot)

    url = '%s/api/%s' % (url_base, get_setting_value('sickrage_api'))

    return sickrage_http() + url


def sickrage_url_no_api():
    port = get_setting_value('sickrage_port')
    url_base = get_setting_value('sickrage_ip')
    webroot = get_setting_value('sickrage_webroot')

    if port:
        url_base = '%s:%s' % (url_base, port)

    if webroot:
        url_base = '%s/%s' % (url_base, webroot)

    return sickrage_http() + url_base


def sickrage_api(params=None, use_json=True, dev=True):
    username = get_setting_value('sickrage_user')
    password = get_setting_value('sickrage_password')

    url = sickrage_url() + params
    r = urllib2.Request(url)

    if username and password:
        base64string = base64.encodestring('%s:%s' % (username, password)).replace('\n', '')
        r.add_header("Authorization", "Basic %s" % base64string)

    data = urllib2.urlopen(r).read()
    if dev:
        print url
        print data
    if use_json:
        data = json.JSONDecoder().decode(data)
    return data

@app.route('/xhr/sickrage/')
def xhr_sickrage():
    params = '/?cmd=future&sort=date'

    try:
        sickrage = sickrage_api(params)

        compact_view = get_setting_value('sickrage_compact') == '1'
        show_airdate = get_setting_value('sickrage_airdate') == '1'

        if sickrage['result'].rfind('success') >= 0:
            sickrage = sickrage['data']
            for time in sickrage:
                for episode in sickrage[time]:
                    episode['image'] = get_pic(episode['indexerid'], 'banner')
    except:
        return render_template('sickrage.html',
            sickrage='',
        )

    return render_template('sickrage.html',
        url=sickrage_url_no_api(),
        app_link=sickrage_url_no_api(),
        sickrage=sickrage,
        missed=sickrage['missed'],
        today=sickrage['today'],
        soon=sickrage['soon'],
        later=sickrage['later'],
        compact_view=compact_view,
        show_airdate=show_airdate,
        
    )

@app.route('/xhr/sickrage/get_banner/<inderxerid>/')
def get_banner(inderxerid):
    params = '/?cmd=show.getbanner&inderxerid=%s' % inderxerid
    img = StringIO.StringIO(sickrage_api(params, use_json=False))
    logger.log('SICKRAGE :: Getting banner %s' % inderxerid, 'DEBUG')
    return send_file(img, mimetype='image/jpeg')


@app.route('/xhr/sickrage/get_poster/<inderxerid>/')
def get_poster(inderxerid):
    params = '/?cmd=show.getposter&inderxerid=%s' % inderxerid
    img = StringIO.StringIO(sickrage_api(params, use_json=False))
    return send_file(img, mimetype='image/jpeg')

# returns a link with the path to the required image from SB
def get_pic(indexerid, style='banner'):
    return '%s/xhr/sickrage/get_%s/%s' % ('http://localhost:7000', style, indexerid)


