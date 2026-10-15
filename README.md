# my-health-data

I'm creating this SMART on FHIR App for my own personal use; it's designed to help me retrieve my own data in FHIR.

No one other than me (Josh Mandel) should share their records with it.

## Dev

* https://parceljs.org/getting_started.html
* `curl -s https://open.epic.com/MyApps/EndpointsJson > src/epic.json`
* add `$(yarn global bin)` to `PATH`
* `yarn install`
* `parcel src/*.html`
* browse to http://localhost:1234/index.html

```
parcel build src/*.html  --public-url https://joshuamandel.com/my-health-data/
git checkout gh-pages
git rm *.html *.js *.map
cp -r dist/* .
git add *.js *.html *.map
git commit -m "Build"
git push
git checkout master
```

## Sample imaging

`imaging/` holds five of my own imaging studies, de-identified as the sample patient "Josh Example" so they can be shared and used as test data. Each study is a directory with one `.tgz` per series; each archive holds that series' DICOM files.

| Directory | Study | Series | Images |
|---|---|---|---|
| `mri-brain-2020/` | MRI brain, 29 Jul 2020 (Hitachi Altaire) | 18 | 267 |
| `ct-abdomen-pelvis-2012/` | CT abdomen and pelvis with contrast, 9 Oct 2012 (GE LightSpeed VCT) | 8 | 458 |
| `xr-wrist-left-2012/` | Radiographs, left wrist, 10 Oct 2012 | 3 | 3 |
| `xr-hand-wrist-right-2012/` | Radiographs, right hand and wrist, 10 Oct 2012 | 3 | 3 |
| `xr-hand-right-2012/` | Radiographs, right hand (portable, in a splint), 10 Oct 2012 | 3 | 3 |

The files were made by `imaging/deid.py` and `imaging/reconstruct.py`, which document exactly what was changed. Their inputs are my original, identified CD and portal exports, which are not published, so only I can re-run them (`uv run imaging/deid.py --out imaging <my export folders>`).

What changed:

- Patient name `Example^Josh`, patient ID `JEXAMPLE01`, birth date reduced to 1 January of the birth year. Age, sex and (on the MRI) weight are as recorded.
- Accession numbers and study IDs replaced with `EXMRI2020`, `EXCT2012` and `EXCR2012A`–`C`.
- Every other person name emptied. Institution, department and station names and addresses, device serial numbers, order and request identifiers, comments, and all private attributes removed.
- Study, series and instance UIDs replaced by new UIDs, derived the same way on every run.
- Dates, times, descriptions, protocols, equipment and all technical attributes kept. The pixel data of every original series kept is unchanged, at full resolution, in the original transfer syntax.
- Rebuilt from scratch, because the originals show my name and identifiers in their pixels. Each is marked "(reconstructed)" in its series description and explains itself in Image Comments:
  - the CT dose report screen, with the original dose values;
  - the CT order form, scanned in with the CT. Patient, clinicians, staff, facility, phone and order numbers are fictional; the clinical content is as written;
  - four MRI viewer screen captures. Two show the same slices as the originals. The other two originals showed localizer images that are not on the CD, so their reconstructions use the nearest series that is.
- Added: a CT radiation dose SR (series 997, "Dose Record (synthetic)"), built from the dose screen's values and the image headers. The CD had none.
- The fonts used for the reconstructions are DejaVu (`imaging/fonts/`, with their license).

The radiographs show the technologists' lead markers (letters and initials), as taken.
