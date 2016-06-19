"""
Tests for rfstream module.
"""
import unittest

from obspy import read, read_events
from obspy.core import AttribDict
from obspy.core.util import NamedTemporaryFile
from rf import read_rf, RFStream, rfstats
from rf.rfstream import (obj2stats, _HEADERS, _STATION_GETTER, _EVENT_GETTER,
                         _FORMATHEADERS)
from rf.util import minimal_example_rf, minimal_example_Srf


_HEADERS_TEST_IO = (50.3, -100.2, 400.3,
                    -20.32, 10., 12.4, 6.5, -40.432,
                    20.643, 57.6, 90.1, 10.2, 10.,
                    10., -20, 150,
                    'Ps', 15.7, 2.5)

_HEADERS_NOT_DETERMINED_BY_RFSTATS = ('moveout', 'box_pos', 'box_length')

FORMATS = _FORMATHEADERS.keys()

try:
    import obspyh5
except ImportError:
    pass
else:
    FORMATS.append('h5')


def write_test_header(stream):
    for tr in stream:
        st = tr.stats
        for head, val in zip(_HEADERS, _HEADERS_TEST_IO):
            if head in ('onset', 'event_time'):
                val = st.starttime + val
            st[head] = val


def test_io_header(testcase, stream, ignore=()):
    for format in FORMATS:
        stream1 = stream.copy()
        suffix = '.' + format.upper()
        if format in ('sac', 'sh'):  # TODO!!
            continue
        if format == 'sh':
            format = 'q'
            suffix = '.QHD'
        with NamedTemporaryFile(suffix=suffix) as ft:
            fname = ft.name
            stream1.write(fname, format.upper())
            stream2 = read_rf(fname)
        st1 = stream1[0].stats
        st2 = stream2[0].stats
        for head in _HEADERS:
            if head in st1 and head not in ignore:
                if head not in st2:
                    from IPython import embed
                    embed()
                testcase.assertIn(head, st2)
                msg = ("AssertionError for header '%s' with format '%s': "
                       "%s and %s not equal within 3 places")
                testcase.assertAlmostEqual(
                    st1[head], st2[head], 3,
                    msg=msg % (head, format, st1[head], st2[head])
                    )
        if len(ignore) == 0 or format != 'q':
            testcase.assertEqual(stream1[0].id, stream2[0].id)


class RFStreamTestCase(unittest.TestCase):

    def setUp(self):
        self.event = read_events()[0]
        self.station = AttribDict({'latitude': 41.818 - 66.7,
                                   'longitude': 79.689,
                                   'elevation': 365.4})

    def test_read_rf(self):
        self.assertIsInstance(read_rf(), RFStream)

    def test_io_header(self):
        stream = RFStream(read())[:1]
        for tr in stream:
            tr.stats.location = '11'
        write_test_header(stream)
        test_io_header(self, stream)

    def test_io_header_obspy_stream(self):
        stream = read()[:1]
        ignore = ('back_azimuth', 'inclination')
        test_io_header(self, stream, ignore=ignore)

    def test_io_header_rf(self):
        stream = minimal_example_rf()[:1]
        test_io_header(self, stream)

    def test_obj2stats(self):
        stats = obj2stats(event=self.event, station=self.station)
        for head, _ in _STATION_GETTER + _EVENT_GETTER:
            self.assertIn(head, stats)

    def test_rfstats(self):
        stats = rfstats(station=self.station, event=self.event, pp_depth=100.)
        for head in _HEADERS:
            if head not in _HEADERS_NOT_DETERMINED_BY_RFSTATS:
                self.assertIn(head, stats)
        # event is exactly north from station and around 66.7 degrees away
        self.assertTrue(abs(stats.distance - 66.7) < 1.)
        self.assertTrue(abs(stats.back_azimuth % 360.) < 0.1)
        self.assertTrue(abs(stats.slowness - 6.4) < 0.1)

    def test_trim2(self):
        stream = read_rf()
        starttimes = [tr.stats.starttime for tr in stream]
        stream.trim2(50, 100, 'starttime')
        for t0, tr in zip(starttimes, stream):
            self.assertEqual(tr.stats.starttime - t0, 50)
            self.assertEqual(tr.stats.endtime - t0, 100)

    def test_slice2(self):
        stream = read_rf()
        endtimes = [tr.stats.endtime for tr in stream]
        stream = stream.slice2(-50, -20, 'endtime')
        for t0, tr in zip(endtimes, stream):
            self.assertEqual(tr.stats.starttime - t0, -50)
            self.assertEqual(tr.stats.endtime - t0, -20)

    def test_minimal_example_rf(self):
        stream = minimal_example_rf()
#        stream.select(component='L').plot_rf()
#        stream.select(component='Q').plot_rf()
#        stream.select(component='T').plot_rf()
#        import matplotlib.pyplot as plt
#        plt.show()
        stack = stream.stack()
        L = stack.select(component='L')
        Q = stack.select(component='Q')
        # check that maximum in L component is at 0s (at P onset)
        onset = L[0].stats.onset - L[0].stats.starttime
        dt = L[0].stats.delta
        self.assertAlmostEqual(L[0].data.argmax() * dt - onset, 0, delta=0.1)
        # check that maximum in Q component is at 8.6s
        # (subducting slab, Northern Chile)
        self.assertAlmostEqual(Q[0].data.argmax() * dt - onset, 8.6, delta=0.2)

    def test_minimal_example_Srf(self):
        stream = minimal_example_Srf()
#        stream.select(component='L').plot_rf()
#        stream.select(component='Q').plot_rf()
#        stream.select(component='T').plot_rf()
#        import matplotlib.pyplot as plt
#        plt.show()
        stack = stream.stack()
        L = stack.select(component='L')
        Q = stack.select(component='Q')
        # check that maximum in Q component is at 0s (at S onset)
        onset = Q[0].stats.onset - Q[0].stats.starttime
        dt = Q[0].stats.delta
        self.assertAlmostEqual(Q[0].data.argmax() * dt - onset, 0, delta=0.1)
        # check that maximum in L component is at 8.6s
        L.trim2(-5, 16, 'onset')
        onset = L[0].stats.onset - L[0].stats.starttime
        self.assertAlmostEqual(L[0].data.argmax() * dt - onset, 8.6, delta=0.2)

    def test_str(self):
        str_ = '6.0M dist:46.1 baz:325.0 slow:6.40 (Ps moveout)'
        stream = minimal_example_rf()
        self.assertEqual(str(stream[0]).split(' | ')[-1], str_)


def suite():
    return unittest.makeSuite(RFStreamTestCase, 'test')


if __name__ == '__main__':
    unittest.main(defaultTest='suite')
