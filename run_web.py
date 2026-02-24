"""Entry point for the Cambio web GUI."""

from web.app import app, socketio

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5050, debug=True, allow_unsafe_werkzeug=True)
