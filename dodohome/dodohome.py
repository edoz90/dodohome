from flask import (Flask, render_template, request, redirect, url_for, jsonify,
                   session)
from support_calendar import (get_latest, token_saver, get_user,
                              get_directions, get_work_location,
                              get_calendar_list)
from requests_oauthlib import OAuth2Session
from redis_session import RedisSessionInterface
import googlemaps

app = Flask(__name__)
app.config["APPLICATION_NAME"] = "dodohome"
app.config.from_envvar("FLASK_CONFIG_FILE")
app.session_interface = RedisSessionInterface()

# ON DEBUG --------
import os
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
app.config["DEBUG"] = True
# ON DEBUG ---------


@app.before_first_request
def session_management():
    # make the session last indefinitely until it is cleared
    session.permanent = True


@app.route("/")
def index():
    if "oauth_token" in session:
        get_user()
        if "page" in request.args:
            page = request.args["page"]
            if page == "vehicles":
                return render_template(
                    "index.html", vehicles=app.config["VEHICLES"])
            elif page == "maps":
                gmaps = googlemaps.Client(key=app.config["GOOGLEMAPS_KEY"])
                location_work_full, location_work = get_work_location(gmaps)
                # Approx home location city by IP
                location_home = gmaps.geolocate()["location"]
                if location_work == -1 or location_work_full == -1:
                    # Ask the user to insert his WORK location
                    return render_template(
                        "index.html",
                        title="Work",
                        maps={
                            "home": location_home,
                            "work": None
                        })
                else:
                    # Ask the user to insert his HOME location
                    if "location_home" in session and "location_home_full" in session:
                        return redirect(url_for("done"))

                    location_work["geometry"]["location"][
                        "full"] = location_work_full

                    return render_template(
                        "index.html",
                        title="Home",
                        maps={
                            "home": location_home,
                            "work": location_work["geometry"]["location"]
                        },
                        marker=location_work_full)
            else:
                return render_template("index.html")
        else:
            return render_template("index.html", calendars=get_calendar_list())
    else:
        return render_template("index.html")


@app.route("/done")
def done():
    try:
        return render_template(
            "done.html",
            locations={
                "home": session["location_home_full"],
                "work": session["location_work_full"],
            },
            vehicles={
                "primary": session["primary_vehicle"],
                "secondary": session["secondary_vehicle"],
            })
    except KeyError:
        return redirect(url_for("index"))


@app.route("/restart")
def restart():
    session.pop("default_calendar", None)
    session.pop("primary_vehicle", None)
    session.pop("secondary_vehicle", None)
    session.pop("location_work_full", None)
    session.pop("location_work", None)
    session.pop("location_home_full", None)
    session.pop("location_home", None)
    return redirect(url_for("index"))


@app.route("/oauth2callback")
def oauth2callback():
    if not ("code" in request.args):
        session.clear()
        import redis
        redis.StrictRedis(host="localhost", port=6379, db=0).flushdb()
        g = OAuth2Session(
            app.config["CLIENT_ID"],
            scope=app.config["SCOPES"],
            redirect_uri=url_for("oauth2callback", _external=True))
        authorization_url, state = g.authorization_url(
            app.config["AUTH_BASE_URL"],
            access_type="offline",
            prompt="consent")
        session["oauth_state"] = state
        return redirect(authorization_url)
    else:
        g = OAuth2Session(
            app.config["CLIENT_ID"],
            state=session["oauth_state"],
            redirect_uri=url_for("oauth2callback", _external=True))
        token = g.fetch_token(
            app.config["TOKEN_URL"],
            client_secret=app.config["CLIENT_SECRET"],
            authorization_response=request.url)
        token_saver(token)
        return redirect(url_for("index"))


@app.route("/setcalendar", methods=["POST"])
def select_calendar():
    cal = request.form["calendars"]
    # Double check all parameters
    if cal in session["calendars"].split(","):
        session["default_calendar"] = cal
        return redirect(url_for("index", page="vehicles"))
    else:
        return redirect(url_for("index"))


@app.route("/view_events", methods=["POST"])
def view_events():
    cal = request.get_json()["cal"]
    # Double check all parameters
    if not (cal in session["calendars"].split(",")):
        cal = None
    r = get_latest(5, cal)
    return jsonify(events=r)


@app.route("/getvehicles", methods=["POST"])
def get_vehicles():
    r = request.get_json()
    return jsonify(
        vehicles=[x for x in app.config["VEHICLES"] if x != r["vehicle"]])


@app.route("/setvehicle", methods=["POST"])
def select_vehicle():
    primary = request.form["primary"]
    secondary = request.form["secondary"]
    # Double check all parameters
    if all(v in app.config["VEHICLES"] for v in [primary, secondary]):
        session["primary_vehicle"] = primary
        session["secondary_vehicle"] = secondary
        return redirect(url_for("index", page="maps"))
    else:
        return redirect(url_for("index"))


@app.route("/sethome", methods=["POST"])
def set_home_location():
    r = request.get_json()
    location_home = r["location"]
    location_home_full = r["location_full"]
    if (location_home and location_home_full
            and "address_components" in location_home
            and "long_name" in location_home["address_components"][0]
            and "geometry" in location_home
            and location_home != session["location_work"]):
        session["location_home"] = location_home
        session["location_home_full"] = location_home_full
        if "location_work" in session and "location_home" in session:
            gmaps = googlemaps.Client(key=app.config["GOOGLEMAPS_KEY"])
            # Get informations directly from gmaps
            directions_result = get_directions(session["location_home_full"],
                                               session["location_work_full"],
                                               gmaps)
            if directions_result != -1:
                """ replicate the informations to client (no python API to do
                    this without double quering)
                """
                req = {
                    "origin": session["location_home_full"],
                    "destination": session["location_work_full"],
                    "travelMode": "DRIVING"
                }
                return jsonify(success=True, direction=req), 200
            else:
                return jsonify(
                    success=False, error="Something went wrong"), 500
        else:
            return jsonify(success=False, error="Missing something"), 200
    else:
        return redirect(url_for("index"))


@app.route("/setwork", methods=["POST"])
def set_work_location():
    r = request.get_json()
    location_work = r["location"]
    location_work_full = r["location_full"]
    if (location_work and location_work_full
            and "address_components" in location_work
            and "long_name" in location_work["address_components"][0]
            and "geometry" in location_work):
        session["location_work"] = location_work
        session["location_work_full"] = location_work_full
        if "location_home" in session:
            gmaps = googlemaps.Client(key=app.config["GOOGLEMAPS_KEY"])
            directions_result = get_directions(session["location_home_full"],
                                               session["location_work_full"],
                                               gmaps)
            if directions_result != -1:
                """ replicate the informations to client (no python API to do
                    this without double quering)
                """
                req = {
                    "origin": session["location_home_full"],
                    "destination": session["location_work_full"],
                    "travelMode": "DRIVING"
                }
                return jsonify(success=True, direction=req), 200
            else:
                return jsonify(
                    success=False, error="Something went wrong"), 500
        else:
            return jsonify(success=True, error="Missing home location"), 200
    else:
        return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.clear()
    import redis
    redis.StrictRedis(host="localhost", port=6379, db=0).flushdb()
    return jsonify(success=True), 200


if "__main__" == __name__:
    app.run(threaded=True)
