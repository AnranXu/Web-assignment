import pymysql
from flask import Flask
from flask import render_template
from flask import request


app = Flask(__name__)

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')
    else:
        userno = request.form.get('userno')
        password = request.form.get('password')
        db = pymysql.connect("localhost", "root", "Tzy794920512", "proxyinfomation")
        cursor = db.cursor()
        sql = "insert into users(UserNo, Password) values (" + userno + ", '" + password + "')"
        cursor.execute(sql)
        db.commit()
        db.close()
        return render_template('login.html')
        db.close()


@app.route('/login', methods=['GET','POST'])
def login():
    global lock, user_buffer
    if request.method == 'GET':
        return render_template('login.html')
    else:
        userno = request.form.get('userno')
        password = request.form.get('password')
        db = pymysql.connect("localhost", "root", "Tzy794920512", "proxyinfomation")
        cursor = db.cursor()
        sql = "select * from users where (UserNo = " + userno + ")and (Password = '" + password + "')"
        cursor.execute(sql)
        results = cursor.fetchall()
        db.close()
        if len(results) == 1:
            str = request.remote_addr
            f = open("user.txt", 'w')
            f.write(str)
            f.close()
            return u'登陆成功'
        else:
            return u'账号或密码错误'
    db.close()


if __name__ == '__main__':
    f = open("user.txt", 'w')
    f.seek(0)
    f.truncate()
    f.close()
    app.run()