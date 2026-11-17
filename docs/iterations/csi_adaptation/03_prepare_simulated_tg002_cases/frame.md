# Signed frame, fixed by reading

The numerical frame is the frame of the source/receiver coordinates in
`functions/ReadFreData.m`: x is radius times cosine, y is radius times
sine. Angle zero lies on positive x; increasing angle turns toward
positive y. For TM, its `meshgrid(ypuni,xpuni)` construction puts numerical
x in the first matrix dimension, numerical y in the second. The exported
primary-coordinate vectors and Fortran-order reshaping preserve that
ordering. Native `imagesc` displays the first dimension vertically, which
does not change the numerical point coordinates.

Belkebir and Saillard's [2001 database introduction](https://doi.org/10.1088/0266-5611/17/6/301)
uses a perspective setup drawing (Figure 3) and unlabelled cross-section
sketches (Figures 6/7). Treating sketch right/up as the numerical x/y axes
in activity 02 was an arbitrary, unregistered frame declaration. It must
not be used as the signed numerical truth. The signed clockwise quarter
turn from that sketch declaration is: sketch up becomes numerical right,
and sketch left becomes numerical up. Thus (x_num,y_num)=(y_sketch,-x_sketch).
No reflection or fitted translation is introduced.
This is a right-handed registration of the sketch declaration, inferred
from the labelled same-file evidence below. The unlabelled perspective
figure alone cannot establish a unique signed Cartesian transformation.

The introduction alone does not print an x/y pair on the cylinder sketch.
For an independent **reading-only sign check**, use database first author
Belkebir with Tijhuis, *Modified2 gradient method and modified Born method
for solving a two-dimensional inverse scattering problem*, Inverse
Problems 17 (2001), 1671-1688,
[author PDF](https://www.fresnel.fr/perso/belkebir/Articles/Ip01_Belkebir.pdf).
Section 4.2.1 identifies `dielTM_dec8f.exp` and places its reconstruction
domain at positive y (centred at y=2.8 cm); Figure 6 has its cylinder near
x=0, positive y, with the plotted vertical coordinates 0.3 to 5.3 cm.
This is published evidence independent of our recovered images. It fixes
the sign that an unlabelled sketch alone cannot establish. We do not use
the published reconstructed 2.8 cm domain centre as exact ground truth.
That companion paper lists approximate transmitter/receiver radii in
reverse order to the CC-CSI driver. Its settings are not imported: our
baseline keeps the shipped transmitter 0.72 m and receiver 0.76 m.

The nominal true cylinder centre in exported numerical coordinates is
therefore **(0,+30) mm**, radius 15 mm, relative permittivity 3 +/-0.3,
using the introduction's **approximately** 30 mm displacement. The paper
does not provide millimetre-accurate surveyed coordinates. The -2.5-degree
term in the shipped first-opus driver corrects transmitter angles only;
receiver angles stay unchanged. It is not a global image-frame rotation,
and is not applied to the truth. No position was inferred by fitting our
output centroid, and no contrast image was moved or rotated.

The former activity-02 JSON remains unchanged as history. Registered
rescoring is saved separately in
`results/csi/preparation/2026-11-17_frame/registered_scores.json`.
At half the signed peak, the nominal registered area errors are 35.123%,
34.223%,38.473% for MF-CC-CSI, MR-CSI,CSI, with centroid errors
4.108,4.054,3.927 mm. Their support areas and mean contrasts are unchanged.
These are errors against nominal experimental geometry, not a claim of
survey accuracy or a new table-C success threshold.
