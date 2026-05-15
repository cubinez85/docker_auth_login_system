from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/')
def hello():
    return jsonify({'message': 'Hello, World!'})

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'service': 'test_app'})

if __name__ == '__main__':
    print("Test app is ready")
    app.run(host='0.0.0.0', port=5000, debug=True)
