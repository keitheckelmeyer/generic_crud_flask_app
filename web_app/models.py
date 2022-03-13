import os
import sqlalchemy as sa
from web_app import db
from flask_wtf import FlaskForm
from wtforms_alchemy import model_form_factory, ModelFormField
from wtforms import HiddenField
from flask_continuum import VersioningMixin
from wtforms.fields import SelectField
import re

ModelForm = model_form_factory(FlaskForm)


class BaseForm(ModelForm):
    obj_id = HiddenField()


class MyBaseModel:

    def name(self):
        return self.__repr__()

    @property
    def sort_name(self):
        return str(self.name).lower()

    def this_model_string(self):
        return re.split('[.\']', str(self.__class__))[-2]

    def get_parent_model(self):
        return None

    def parent_model_string(self):
        parent_model = self.get_parent_model()
        if not parent_model:
            return
        return re.split('[.\']', str(parent_model))[-2]

    def parent(self):
        model = self.get_parent_model()
        if not model:
            return
        model_string = re.split('[.\']', str(model))[-2]
        model = eval(model_string)
        query = db.session.query(model).filter(model.id == eval(f"self.{model_string.lower()}_id"))
        return query.first()

    def parent_list(self):
        model = self.get_parent_model()
        if not model:
            return []
        model_string = re.split('[.\']', str(model))[-2]
        Model = eval(model_string)
        query = db.session.query(Model)
        return query.all()


    def parent_choices(self):
        parent_list = self.parent_list()
        if not parent_list:
            return [('', '')]
        choices = [(p.id, p) for p in parent_list]
        sorted_choices = sorted(choices, key=lambda x: x[1].sort_name)
        return sorted_choices

    def get_child_model(self):
        return None

    def child_model_string(self):
        child_model = self.get_child_model()
        if not child_model:
            return
        return re.split('[.\']', str(child_model))[-2]


    def children(self):
        model = self.get_child_model()
        if not model:
            return
        model_string = re.split('[.\']', str(model))[-2]
        this_model_string = self.this_model_string()
        query = model.query.join(eval(this_model_string)).filter(eval(f"model.{this_model_string.lower()}_id") == self.id)
        return query.all()


class Filepath(MyBaseModel, db.Model, VersioningMixin):
    id = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String(255), unique=True, nullable=False)

    def __repr__(self):
        return self.path

    @property
    def name(self):
        return self.path


class FilepathForm(BaseForm):
    class Meta:
        model = Filepath
        include_foreign_keys = True


class Subpath(MyBaseModel, db.Model, VersioningMixin):
    id = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String(255), unique=True, nullable=False)
    filepath_id = db.Column(db.Integer, db.ForeignKey('filepath.id'), nullable=False)
    filepath = db.relationship('Filepath', foreign_keys=[filepath_id]) # , back_populates='subpaths')

    def __repr__(self):
        return f"{self.filepath}\\{self.path}"

    @property
    def name(self):
        return self.path

    def get_parent_model(self):
        return Filepath

    def get_child_model(self):
        return File


class SubpathForm(BaseForm):
    class Meta:
        model = Subpath
        include_foreign_keys = True


class Artist(MyBaseModel, db.Model, VersioningMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)

    def __repr__(self):
        return self.name

    def get_child_model(self):
        return Album


class ArtistForm(BaseForm):
    class Meta:
        model = Artist
        include_foreign_keys = False


class Album(MyBaseModel, db.Model, VersioningMixin):
    id = db.Column(db.Integer, primary_key=True)
    artist_id = db.Column(db.Integer, db.ForeignKey('artist.id'), nullable=False)
    artist = db.relationship('Artist', foreign_keys=[artist_id])
    name = db.Column(db.String(150), unique=False, nullable=False)
    release_year = db.Column(db.Integer, nullable=True)

    def __repr__(self):
        return f"({self.artist}) {self.name}"

    def get_child_model(self):
        return File

    def get_parent_model(self):
        return Artist


class AlbumForm(BaseForm):
    class Meta:
        model = Album
        include_foreign_keys = True

    artist_id = SelectField("Artist", choices=[], validate_choice=False)


class File(MyBaseModel, db.Model, VersioningMixin):
    id = db.Column(db.Integer, primary_key=True)
    subpath_id = db.Column(db.Integer, db.ForeignKey('subpath.id'), nullable=False, unique=False)
    subpath = db.relationship('Subpath', foreign_keys=[subpath_id])
    album_id = db.Column(db.Integer, db.ForeignKey('album.id'), nullable=True, unique=False)
    album = db.relationship('Album', foreign_keys=[album_id])
    name = db.Column(db.String(150), unique=False, nullable=False)
    order = db.Column(db.Integer, nullable=True)
    __table_args__ = (db.UniqueConstraint(
        'subpath_id', 'name', name='_subpath_name_uc'),
    )

    def __repr__(self):
        return self.name

    def get_parent_model(self):
        return Album

    def get_child_model(self):
        return Datafile


class FileForm(BaseForm):
    class Meta:
        model = File
        include_foreign_keys = False

    album_id = SelectField("Album", choices=[], validate_choice=False)


class Datafile(MyBaseModel, db.Model, VersioningMixin):
    id = db.Column(db.Integer, primary_key=True)
    subpath_id = db.Column(db.Integer, db.ForeignKey('subpath.id'), nullable=False)
    subpath = db.relationship('Subpath', foreign_keys=[subpath_id])
    file_id = db.Column(db.Integer, db.ForeignKey('file.id'), nullable=False, unique=True)
    file = db.relationship('File', foreign_keys=[file_id])
    name = db.Column(db.String(150), unique=False, nullable=True)
    min = db.Column(db.Float)
    max = db.Column(db.Float)

    def get_parent_model(self):
        return File


class DatafileForm(BaseForm):
    class Meta:
        model = Datafile
        include_foreign_keys = True


sa.orm.configure_mappers()
