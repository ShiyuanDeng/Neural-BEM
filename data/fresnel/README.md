# Institut Fresnel 2001 dielectric data

These are the 14,112-row single-cylinder and two-cylinder measurement tables
from a public teaching mirror. Both contain the expected complete
8-frequency × 36-transmitter × 49-receiver acquisition. Raw bytes are preserved;
the mirror's `.txt` suffix was changed to `.exp`. It omits the original header.

[provenance.json](provenance.json) records the pinned mirror revision, exact
download URLs, sizes and SHA256 hashes. The official IOP article endpoint
returned a CAPTCHA page on retrieval; comparison against the original
supplementary archive remains unavailable. These files are therefore identified
as mirrored measurements, not independently authenticated publisher originals.

Institut Fresnel describes the first-opus data as free for scientific use on
its [database page](https://www.fresnel.fr/3Ddatabase/). Cite Belkebir & Saillard,
*Inverse Problems* **17** (2001), 1565–1571,
[DOI 10.1088/0266-5611/17/6/301](https://doi.org/10.1088/0266-5611/17/6/301).

The [primary description, §6](https://www.fresnel.fr/perso/belkebir/Articles/Ip01Introduction_Belkebir.pdf)
defines columns as transmitter label, receiver label, physical GHz, real/imaginary
**total** field, real/imaginary incident field. Its convention is exp(+iωt).
Receiver labels denote absolute angles on a 72-position ring. The importer
conjugates once, subtracts incident from total, and selects the correct 49 pairs.

Do not reuse the mirror's Python loader: inspection found that it labels total
fields as scattered and maps frequency labels through an unrelated lookup table.
The new importer follows the original publication and the actual table labels.

No synthetic observations are stored in this directory.
