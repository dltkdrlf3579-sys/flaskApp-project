from flask import Flask

app = Flask(__name__)

@app.route('/test')
def test():
    with open('TEST_WORKED.txt', 'w') as f:
        f.write('YES!')
    return 'TEST'

@app.route('/partner-accident')
def partner_accident():
    with open('PA_WORKED.txt', 'w') as f:
        f.write('YES!')
    return 'PARTNER ACCIDENT'

if __name__ == '__main__':
    app.run(port=5002, debug=True)