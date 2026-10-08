"""Public macOS FSEvents hints; bounded dirty roots, never byte/ownership claims."""
from __future__ import annotations
import ctypes as C
import os
from pathlib import Path
import sys
import threading
import time


class NativeStream:
    def __init__(self, paths, state, exclusions):
        self.paths=tuple(paths);self.root_set=set(paths);self.state=str(state);self.exclusions=set(exclusions)
        self.dirty=set();self.lock=threading.Lock();self.stop=threading.Event();self.ready=threading.Event()
        self.error=None;self.healthy=False;self.losses=0;self.batches=0
        self.thread=threading.Thread(target=self.run,daemon=True,name='footprint-fsevents');self.thread.start()
        if not self.ready.wait(2):self.error='native_start_timeout';self.close()

    def run(self):
        stream=None;array=None;strings=[];started=False;loop=None;mode=None
        try:
            cf=C.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
            fs=C.CDLL('/System/Library/Frameworks/CoreServices.framework/CoreServices')
            callback_type=C.CFUNCTYPE(None,C.c_void_p,C.c_void_p,C.c_size_t,C.c_void_p,C.POINTER(C.c_uint32),C.POINTER(C.c_uint64))
            def callback(_stream,_context,n,event_paths,flags,_ids):
                try:
                    values=C.cast(event_paths,C.POINTER(C.c_char_p));dirty=set();loss=False
                    for i in range(n):
                        # Dropped/wrapped events or a moved root invalidate all watched-root hints.
                        if flags[i]&0xef:loss=True;continue
                        path=os.fsdecode(values[i]).rstrip('/')
                        if path==self.state or path.startswith(self.state+'/') or self.exclusions.intersection(path.split('/')):continue
                        while path and path!='/':
                            if path in self.root_set:dirty.add(path);break
                            path=path.rpartition('/')[0]
                    with self.lock:
                        self.dirty.update(self.paths if loss else dirty);self.batches+=1;self.losses+=int(loss)
                except Exception:
                    with self.lock:self.dirty.update(self.paths);self.losses+=1
            self.callback=callback_type(callback)
            cf.CFStringCreateWithCString.argtypes=[C.c_void_p,C.c_char_p,C.c_uint32];cf.CFStringCreateWithCString.restype=C.c_void_p
            cf.CFArrayCreate.argtypes=[C.c_void_p,C.POINTER(C.c_void_p),C.c_long,C.c_void_p];cf.CFArrayCreate.restype=C.c_void_p
            cf.CFRelease.argtypes=[C.c_void_p];cf.CFRelease.restype=None
            cf.CFRunLoopGetCurrent.argtypes=[];cf.CFRunLoopGetCurrent.restype=C.c_void_p
            cf.CFRunLoopRunInMode.argtypes=[C.c_void_p,C.c_double,C.c_ubyte];cf.CFRunLoopRunInMode.restype=C.c_int32
            fs.FSEventStreamCreate.argtypes=[C.c_void_p,callback_type,C.c_void_p,C.c_void_p,C.c_uint64,C.c_double,C.c_uint32];fs.FSEventStreamCreate.restype=C.c_void_p
            fs.FSEventStreamScheduleWithRunLoop.argtypes=[C.c_void_p,C.c_void_p,C.c_void_p];fs.FSEventStreamScheduleWithRunLoop.restype=None
            fs.FSEventStreamStart.argtypes=[C.c_void_p];fs.FSEventStreamStart.restype=C.c_ubyte
            for name in ('FSEventStreamStop','FSEventStreamInvalidate','FSEventStreamRelease'):
                getattr(fs,name).argtypes=[C.c_void_p];getattr(fs,name).restype=None
            fs.FSEventStreamUnscheduleFromRunLoop.argtypes=[C.c_void_p,C.c_void_p,C.c_void_p];fs.FSEventStreamUnscheduleFromRunLoop.restype=None
            for path in self.paths:
                value=cf.CFStringCreateWithCString(None,os.fsencode(path),0x08000100)
                if not value:raise OSError('native_path_allocation_failed')
                strings.append(value)
            pointers=(C.c_void_p*len(strings))(*strings)
            callbacks=C.addressof(C.c_byte.in_dll(cf,'kCFTypeArrayCallBacks'))
            array=cf.CFArrayCreate(None,pointers,len(strings),callbacks)
            if not array:raise OSError('native_array_allocation_failed')
            # SinceNow: a new listener starts before baseline scanning; no event replay claim.
            stream=fs.FSEventStreamCreate(None,self.callback,None,array,2**64-1,1.0,0x16)
            if not stream:raise OSError('native_stream_creation_failed')
            loop=cf.CFRunLoopGetCurrent();mode=C.c_void_p.in_dll(cf,'kCFRunLoopDefaultMode').value
            fs.FSEventStreamScheduleWithRunLoop(stream,loop,mode)
            if not fs.FSEventStreamStart(stream):raise OSError('native_stream_start_failed')
            started=True;self.healthy=True;self.ready.set()
            while not self.stop.is_set():cf.CFRunLoopRunInMode(mode,.5,False)
        except Exception as exc:self.error=type(exc).__name__+': '+str(exc)[:160]
        finally:
            self.healthy=False;self.ready.set()
            if stream:
                if started:fs.FSEventStreamStop(stream)
                if loop and mode:fs.FSEventStreamUnscheduleFromRunLoop(stream,loop,mode)
                fs.FSEventStreamInvalidate(stream);fs.FSEventStreamRelease(stream)
            if array:cf.CFRelease(array)
            for value in strings:cf.CFRelease(value)

    def drain(self):
        with self.lock:result=self.dirty.copy();self.dirty.clear()
        return result

    def close(self):
        self.stop.set();self.thread.join(timeout=2)


class Watcher:
    def __init__(self):
        self.native=None;self.signature=None;self.retry_at=0;self.reason='initializing'
    def update(self,paths,config,one_shot=False):
        available=tuple(sorted(p for p in paths if Path(p).is_dir() and not Path(p).is_symlink()))
        native=not one_shot and config['monitor']['event_backend']=='auto' and sys.platform=='darwin'
        signature=(native,available,tuple(sorted(config['exclude_names'])),str(config['data_dir']))
        changed=signature!=self.signature
        if changed:
            self.close();self.signature=signature;self.retry_at=0
        if not native:
            self.reason='one_shot' if one_shot else 'configured_polling' if config['monitor']['event_backend']=='polling' else 'unsupported_platform'
        elif not available:self.reason='no_existing_roots'
        elif (not self.native or not self.native.healthy) and time.time()>=self.retry_at:
            self.close();self.native=NativeStream(available,config['data_dir'],config['exclude_names'])
            self.retry_at=time.time()+30;self.reason=self.native.error
            # Restarted/changed listeners may have a gap: force all roots through the bounded scheduler.
            changed=True
        return set(paths) if changed else set()
    def drain(self):return self.native.drain() if self.native else set()
    def status(self):
        healthy=bool(self.native and self.native.healthy)
        return {'backend':'fsevents' if healthy else 'polling','healthy':healthy,
                'fallback_reason':None if healthy else (self.native.error if self.native and self.native.error else self.reason),
                'watched_roots':len(self.native.paths) if healthy else 0,'event_batches':self.native.batches if self.native else 0,
                'loss_rescans':self.native.losses if self.native else 0,'scope':'changed monitored roots; bounded full-root measurement, no per-file delta cache or persistent replay'}
    def close(self):
        if self.native:self.native.close();self.native=None
