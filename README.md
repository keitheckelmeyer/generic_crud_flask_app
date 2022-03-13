# generic_crud_flask_app

I wanted a faster, more generic way to handle dealing with boilerplate code for data rather than have to write a route for each object class 
(and ultimately as a template for new projects) 

Ugh! 

Instead, I built a generic model that I use as a mixin that defines any basic parent/child relationships. And each specific
class simply has to define (override) a class for parent and/or child relationship as applicable. 

I applied this to my music library (there is some custom logic due to the fie layout where I had music files stored in two different locations), 
but primarily it boiled down to artist/album/song.

Ultimately, I'll transform audio files into MFCC for deep learning exercises.

This prepwork will build the files I can then upload to Google collab and use GPU and/or TPU recourses.
