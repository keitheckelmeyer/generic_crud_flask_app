import os.path
import traceback
import sqlalchemy
from flask import Blueprint, render_template, redirect, jsonify, request, flash, url_for
from web_app import app, db, executor
from web_app.models import Album, Artist, File, Filepath, Subpath, Datafile
from web_app.models import AlbumForm, ArtistForm, FileForm, FilepathForm, SubpathForm, DatafileForm
import glob, re
import datetime, time
from web_app.preprocess import PreprocessPipeline
from web_app.preprocess import Loader, Padder, LogSpectrogramExtractor, MinMaxNormalizer, Saver

main = Blueprint('main', __name__, url_prefix="/", template_folder='/templates', static_folder="/static")
process_list = []

extensions = ['mp3', 'flac', 'wma', ]


@main.route("/home", methods=['GET'])
@main.route("/", methods=['GET'])
def home():

    # Get all models
    # https://stackoverflow.com/questions/26514823/get-all-models-from-flask-sqlalchemy-db/26518401
    models = [mapper.class_.__name__ for mapper in db.Model.registry.mappers]

    # filter out the audit tables & sort
    models = list(filter(lambda x: not x.endswith('Version'), models))
    models = sorted(models, key=lambda x: x)

    # Get active background processes
    # todo: Still need to look more into how this works
    procs = []
    futures = []
    done = []
    for process in process_list:
        if not executor.futures.done(process):
            procs.append(f"{process}:{executor.futures._state(process)}")
            done.append(process)
        else:
            futures.append(executor.futures.pop(process))
    for d in done:
        process_list.remove(d)

    return render_template("home.html", items=models, procs=procs, futures=futures)


@main.route("/crud/<string:object_>", methods=['GET', 'POST'])
@main.route("/crud/<string:object_>/<int:obj_id>", methods=['GET', 'POST'])
def crud_object(object_, obj_id=None):

    def pop_choices(Object_, form, relation='parent'):
        """
        populates the form's select box options based on the object(model's) defined relationship(s)
        and the relation parameter.
        :param Object_:
        :param form: the form that needs the select box for
        :param relation: the relation to use as defined in the Object's model class
        :return: the form now populated with select box options and the object's class as a string for display purposes
        """
        options = None
        obj_string = None
        if relation == 'parent':
            obj_inst = db.session.query(Object_).first()
            if not obj_inst:
                return form, None
            obj_string = obj_inst.parent_model_string() or None
            options = obj_inst.parent_choices() or None
        if relation == 'child':
            obj_string = Object_.child_model_string()
        try:
            eval(f"form.{obj_string.lower()}_id").choices = options
        except:
            print(traceback.format_exc())
        return form, obj_string

    def prepop_choices(Obj, obj, form, relation='parent'):
        form, obj_string = pop_choices(Obj, form, relation)
        try:
            eval(f"form.{obj_string.lower()}_id").default = obj.id
            form.process()
        except:
            print(traceback.format_exc())
        return form

    Object = eval(object_)

    form = None
    obj = None
    action = None
    parent = None
    children = None
    Form = eval(f"{object_}Form")
    obj_list = None
    obj_list_type = object_
    if request.method == 'GET':
        #Retrieving an exising object and filling a form
        if obj_id:
            action = 'Review/Edit/Delete'
            try:
                db.session.rollback()
                db.session.commit()
            except:
                pass
            obj = db.session.query(Object).filter(Object.id == obj_id).first()
            form = Form(obj=obj)
            form = prepop_choices(Object, obj, form)
            form.obj_id.data = obj_id
            parent = obj.parent()
            children = obj.children()
            obj_list_type = obj.child_model_string()
        #Retrieiving a blank form
        else:
            obj_list = db.session.query(Object).all()
            action = 'Add'
            form = Form()
            form, obj_string = pop_choices(Object, form)
            children = obj_list
            obj_list_type = object_
    elif request.method == 'POST':
        form = Form()
        if form.validate():
            obj = Object()
            form.populate_obj(obj)
            # if it's prepopulated, we want to update that object
            if form.obj_id.data.isnumeric():
                obj.id = int(form.obj_id.data)
                db.session.merge(obj)
            else:
                db.session.add(obj)
            try:
                db.session.commit()
                flash('Successfully added record.', 'success')
                return redirect(url_for('main.crud_object', object_=object_))
            except:
                print(traceback.format_exc())
                db.session.rollback()
                flash('Error. Record was not added.', 'danger')
            return redirect(url_for('main.crud_object', object_=object_, obj_id=obj.id))
        else:
            flash('Error.', 'danger')
    elif request.method == 'PUT':
        pass
    elif request.method == 'DELETE':
        pass

    try:
        db.session.rollback()
        db.session.commit()
    except:
        pass

    #if obj_list:
    #    obj_list = sorted(obj_list, key=lambda x: x.sort_name)

    return render_template("crud.html",
                           form=form,
                           obj_list=obj_list,
                           obj_list_type=obj_list_type,
                           action=action,
                           obj_type=object_,
                           parent=parent,
                           children=children)


def music_scan(filepaths):
    """

    :param filepaths: filepath to scan to add files and relative subpaths to database
    :return:
    """
    app.logger.info(f'Started Background process: scanning <{filepaths}> for files.')
    file_count = 0
    start_time = time.time()
    for filepath in filepaths:
        all_files = glob.glob(glob.escape(filepath.path) + r'\**\*.*', recursive=True)
        print(len(all_files))
        for one_file in all_files:
            if os.path.isfile(one_file):
                print(f"file: {one_file}")
                file_count += 1
                sub_id = None
                file_name = os.path.basename(one_file)
                file_path = one_file.replace('\\' + file_name, '')
                sub_path = file_path.replace(filepath.path, '')
                try:
                    subpath = Subpath(
                        path=sub_path,
                        filepath_id=filepath.id
                    )
                    db.session.add(subpath)
                    db.session.commit()
                    sub_id = subpath.id
                    print(f"new subpath added: {subpath}")
                except sqlalchemy.exc.IntegrityError:
                    # if we get this error, it's because of a duplicate, and we don't want those
                    db.session.rollback()
                    #print(traceback.format_exc())
                    subpath = db.session.query(Subpath).filter(Subpath.path == sub_path).first()
                    sub_id = subpath.id
                    print(f"existing subpath retrieved: {subpath}")
                    #filename = one_file.split("\\")[-1]
                except:
                    print(f"****no subpath***")
                try:
                    file = File(subpath_id=sub_id, name=file_name)
                    db.session.add(file)
                    db.session.commit()
                    print(f"file saved: {file}")
                except sqlalchemy.exc.IntegrityError:
                    # if we get this error, it's because of a duplicate, and we don't want those
                    db.session.rollback()
                    #print(traceback.format_exc())
                    print(f"file not saved (duplicate)")
                except:
                    print(f"file not saved (other)")
                    print(traceback.format_exc())

    end_time = time.time()
    execution_time = (end_time - start_time)/60
    print(f"Done file scanning. Files: {file_count}. Run time (approx minutes): {execution_time} ")


@main.route("/scan_music_files", methods=['GET'])
def initial_music_scan():
    filepaths = db.session.query(Filepath).all()
    dtn = datetime.datetime.now()
    executor.submit_stored(f'music_scan_{dtn}', music_scan, filepaths)
    process_list.append(f'music_scan_{dtn}')
    flash('Scan started.', 'success')
    return redirect(url_for('main.home'))


def pop_aa():
    """
    This function queries all the files in the database and for music files, will populate/relate to album and artist
    objects
    :return:
    """
    app.logger.info('Started Background process: Populating Artists and Albums.')
    start_time = time.time()

    files = db.session.query(File).all()
    print(f"{len(files)=}")
    for file in files:
        #Due to poor file management, there is some custom logic to best parse artists and albums
        if (file.name.split('.'))[-1].lower() in extensions:
            parts = str(file.subpath).split("\\")
            print(f"{parts=}")
            album_name = None
            album_id = None
            artist_name = None
            artist_id = None
            if len(parts) >= 3:
                if len(parts) >= 5:
                    if parts[4] == '_MUSIC_':
                        artist_name = parts[5]
                    else:
                        artist_name = parts[4]
                album_name = parts[-2]

                try:
                    artist = Artist(name=artist_name)
                    db.session.add(artist)
                    db.session.commit()
                    artist_id = artist.id
                except sqlalchemy.exc.IntegrityError:
                    db.session.rollback()
                    #db.session.commit()
                    artist = db.session.query(Artist).filter(Artist.name == artist_name).first()
                    artist_id = artist.id
                try:
                    album = Album(artist_id=artist_id, name=album_name)
                    db.session.add(album)
                    db.session.commit()
                except sqlalchemy.exc.IntegrityError:
                    db.session.rollback()
                    #db.session.commit()
                    album = db.session.query(Album).filter(Album.name == album_name).first()

                    try:
                        file.album_id = album.id
                        db.session.merge(file)
                        db.session.commit()
                    except sqlalchemy.exc.IntegrityError:
                        print("failed merging/updating file record with album information")
                        db.session.rollback()

    end_time = time.time()
    execution_time = (end_time - start_time) / 60
    print(f"Done file/album/artist pop. Run time (approx minutes): {execution_time} ")
    print("done pop")


@main.route("/pop", methods=['GET'])
def initial_artist_album_pop():
    dtn = datetime.datetime.now()
    executor.submit_stored(f'pop_{dtn}', pop_aa)
    flash('Scan complete.', 'success')
    return redirect(url_for('main.home'))

"""def make_datafile(file_id):
    file = db.session.query(File).filter(File.id == file_id).first()
    file_path = f"{file.subpath.filepath}/{file.subpath.path}"
    fullpath = f"{file.subpath.filepath}/{file.subpath.path}/{file.name}"
    loader = praudio.io.Loader(mono=False)
    signal = loader.load(fullpath)
    dat = Datafile(
        subpath_id=file.subpath_id,
        file_id=file.id,
        name=''
    )"""


def make_artist_datafiles(artist_string, preprocess_pipeline):
    print(artist_string)
    print(preprocess_pipeline)
    start_time = time.time()

    artists = db.session.query(Artist).all()
    artists = list(filter(lambda x: x.name.lower().find(artist_string) != -1, artists))
    print(f"{len(artists)=}")
    print(artists)

    album_list = []
    for a in artists:
        album_list.extend(db.session.query(Album).filter(Album.artist_id == a.id).all())
    print(f"{len(album_list)=}")
    print(album_list)

    file_list = []
    for a in album_list:
        files = db.session.query(File).filter(File.album_id == a.id).all()
        print(f"id: {a.id}, qty: {len(files)=}")
        file_list.extend(files)
    print(f"{len(file_list)=}")

    file_list = list(filter(lambda x: x.album_id is not None, file_list))

    #files = db.session.query(File).filter(File.album.).all()
    FRAME_SIZE = 512
    HOP_LENGTH = 256
    Duration = .74
    SAMPLE_RATE = 22050
    MONO = True
    loader = Loader(SAMPLE_RATE, Duration, MONO)
    padder = Padder()
    log_spectrogram_extractor = LogSpectrogramExtractor(FRAME_SIZE, HOP_LENGTH)
    min_max_normalizer = MinMaxNormalizer(0, 1)
    saver = Saver()

    preprocess_pipeline.loader = loader
    preprocess_pipeline.padder = padder
    preprocess_pipeline.extractor = log_spectrogram_extractor
    preprocess_pipeline.normalizer = min_max_normalizer
    preprocess_pipeline.saver = saver

    dict_list = preprocess_pipeline.process(file_list)
    for d in dict_list:
        try:
            datafile = Datafile(
                subpath_id=d['subpath_id'],
                file_id=d['file_id'],
                name=d['name'],
                min=d['min'],
                max=d['max']
            )
            db.session.add(datafile)
            db.session.commit()
        except:
            db.session.rollback()
            print(traceback.format_exc())
            print(f"error saving: {d}")
            break
    end_time = time.time()
    execution_time = (end_time - start_time) / 60
    print(f"Done file scanning. Files: {len(dict_list)}. Run time (approx minutes): {execution_time} ")


@main.route("/spec/<string:artist>", methods=['GET'])
def start_artist_datafiles(artist):
    dtn = datetime.datetime.now()
    preprocess_pipeline = PreprocessPipeline()
    executor.submit_stored(f'mad_{dtn}', make_artist_datafiles, artist, preprocess_pipeline)
    flash('Datafiles started.', 'success')
    return redirect(url_for('main.home'))
