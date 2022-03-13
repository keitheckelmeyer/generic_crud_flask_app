#import quart.flask_patch
#from quart import Quart
from flask import Flask
from flask_sqlalchemy import SQLAlchemy         # Because I like my data represented as classes when working in python (put sometimes raw SQL is best)
from sqlite3 import dbapi2 as sqlite3
from flask_admin import Admin, BaseView         # Because before I tried the generic thing, I didn't see a reason to make my own forms
from flask_admin.contrib.sqla import ModelView
from flask_bootstrap import Bootstrap           # Front ends aren't my strength
from flask_executor import Executor             # long running processes
from datetime import datetime
from flask_continuum import Continuum           # Something new (for me) to play with (db audit history)

#app = Quart(__name__)
app = Flask(__name__)
app.config.update({
    'SECRET_KEY': 'secret',
    'SQLALCHEMY_DATABASE_URI': 'sqlite:///web_app.db',    # File-based SQL database
    'SQLALCHEMY_TRACK_MODIFICATIONS': False,
    'EXECUTOR_TYPE': 'process',
    'EXECUTOR_PROPAGATE_EXCEPTIONS': True,
})

db = SQLAlchemy(app)
admin = Admin(app)
Bootstrap(app)
executor = Executor(app)
continuum = Continuum(app, db)

from web_app.routes import main
app.register_blueprint(main)

try:
    pass
    #db.drop_all()
except:
    pass
db.create_all()

from web_app.models import Album, Artist, File, Filepath, Subpath, Datafile
admin.add_view(ModelView(Album, db.session))
admin.add_view(ModelView(Artist, db.session))
admin.add_view(ModelView(Filepath, db.session))
admin.add_view(ModelView(Subpath, db.session))
admin.add_view(ModelView(File, db.session))
admin.add_view(ModelView(Datafile, db.session))


if __name__ == "__main__":
    app.run()
