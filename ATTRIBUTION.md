# Attribution

Anatomical model data in this project derives from:

**Z-Anatomy** — https://github.com/Z-Anatomy
Licensed CC BY-SA 4.0. Created by Gauthier Kervyn and contributors.

Z-Anatomy is itself derived from:

**BodyParts3D** — Database Center for Life Science (DBCLS), Japan
Licensed CC BY-SA 2.1 Japan.

Structure naming follows Terminologia Anatomica (TA2, 2019).

Any derivative of these models distributed from this repository is
licensed CC BY-SA 4.0 in accordance with the share-alike terms.

---

## Additional upstream attributions

The paragraphs above are the required chain. Z-Anatomy's own `License.txt`
declares further third-party sources adapted into the models, and they do not
all carry the same terms:

- **"Brainder"** and **"White matter"** — University of Washington
- **"Cranial Nerves and Foramina"** — University of Dundee, CAHID — CC BY 4.0
- **"Anatomy of the Inner Ear"** — University of Dundee School of Medicine —
  **CC BY-NC-SA 4.0**
- **"Kidney"** — Lissie Cowley — **CC BY-NC 4.0**
- Structure definitions — Wikipedia, CC BY-SA 3.0

> **Two of these are non-commercial.** A blanket "everything here is CC BY-SA
> 4.0" claim is therefore not accurate for the whole model. The inner ear and
> kidney components are NC-encumbered upstream, and NC is not compatible with
> CC BY-SA 4.0's share-alike terms.
>
> This does not affect the object inventory in this repository — object names
> are standard anatomical terminology (TA2) and triangle counts and bounding
> boxes are measurements, neither of which is a creative derivative of those
> meshes. **It does affect any distributed mesh derivative**, which is the
> point of the two-tier viewer this repo is heading towards.
>
> The MVMT structure map references no inner-ear or kidney structure, so the
> simplest resolution is to exclude those components from anything exported.
> That decision is not made here — it is recorded so it is not discovered late.
