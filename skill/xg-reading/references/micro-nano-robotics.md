# Micro/nano robotics and active delivery

Use this module by applicability. For each claim, state which claim and system it covers, which evidence that claim requires, and what the evidence gap limits. A paper may validate only one layer — propulsion, navigation, retention, release, or therapy; do not require checks that its claims do not need, and do not write a generic "insufficient characterization" when a missing item limits only one conclusion.

## System classification

- Identify the platform: particle-based microrobot, magnetic helix or corkscrew, catalytic Janus motor, acoustic or ultrasound-driven swimmer, optically driven structure, biohybrid robot (sperm, bacteria, cell), soft or DNA robot, or a delivery vehicle with an active propulsion component.
- Identify the energy source (magnetic, acoustic, optical, chemical, electrical, thermal, biological) and the claimed capability: propulsion, navigation, localization, retention, cargo release, or therapy. Do not require the paper to validate layers it does not claim.
- In the document's material-system table, separate structurally distinct components: actuation core, cargo carrier, targeting ligand, imaging label, protective or stealth layer, and any catalytic or stimuli-responsive element. Separate the role the authors design a component for from the role they experimentally demonstrate; a designed role needs control or functional evidence before it is stated as achieved.
- Distinguish the robot, its cargo, and its surface chemistry when interpreting efficacy or targeting; a paper may optimize one while leaving the others unvalidated.

## Actuation and propulsion

- Applicable claims: propulsion mechanism, speed or controllability, motion in biological fluids. Apply these checks only to the motion and propulsion claims the paper makes.
- Evidence to check: field parameters and calibration (magnetic field strength, gradient and frequency; acoustic pressure and frequency; laser power and wavelength; fuel concentration; pH or temperature) against the stated physiological or safety window; quantitative motion metrics (speed, step length, directionality or rotational diffusion, mean squared displacement, track duration, number of particles or tracks analysed); control particles without the propulsion component; motion in buffer or water compared with biological fluids (serum, mucus, blood, extracellular matrix), where viscosity, flow, protein corona, and confinement can change or abolish propulsion.
- If missing: motion claims remain limited to the conditions actually demonstrated. Static magnetic guidance by a field gradient is not the same mechanism as rotating or swimming propulsion; a guidance experiment does not establish a propulsion claim. Ask whether the observed motion could be passive sedimentation, Brownian diffusion, fluid flow, or boundary effects; control particles without the propulsion component are the direct test.

## Navigation, control, and imaging

- Applicable claims: "targeted navigation", "closed-loop control", in vivo localization, retention, or clearance.
- Evidence to check: open-loop versus closed-loop control, feedback modality, localization accuracy, and the trajectory or path error the claim implies, demonstrated in a biologically relevant medium and geometry; whether the signal comes from the intact robot, from its cargo, or from free label or tissue background; tracer stability (dye leakage, quenching, label detachment); imaging modality and resolution (fluorescence, MRI, ultrasound, photoacoustic, PET/CT); a time course matched to the claim; control particles or labels. Longitudinal imaging and ex vivo analysis (for example ICP-MS, fluorescence of excised organs, or histology) can complement each other; do not present one fixed combination as universally required.
- If missing: a paper that only reports speed or field-driven motion is not required to show a navigation loop; state that navigation was not claimed. A single post-injection time point does not establish navigation, retention, or clearance; label-only signal does not establish intact-robot localization, and static accumulation alone does not establish navigation.
- For swarm or collective claims, check density dependence, aggregation and disaggregation, and whether individual behavior — not only a bulk signal — is controlled.

## Cargo loading, targeting, and release

- Applicable claims: loading capacity, encapsulation efficiency, surface conjugation, triggered release, active or passive targeting, functional delivery.
- Evidence to check: cargo integrity after loading and after release; the release trigger (pH, enzyme, ROS, GSH, light, heat, magnetic field, ultrasound) against physiological ranges, kinetics, and time scales; for targeting claims, receptor dependence (blocking antibody or receptor-negative cells), ligand density, and nonspecific protein-corona effects; distinguish passive accumulation (enhanced permeability and retention), external magnetic or other field guidance, and active ligand-receptor targeting, and measure them separately when the paper claims more than one; distinguish accumulation in a tissue from penetration into it, and from intracellular delivery; cargo-free, robot-free, and ligand-free controls when the claim isolates one component; functional delivery evidence beyond signal detection — excluding free reporter and showing a cargo-dependent effect.
- If missing: detecting a reporter signal supports presence or association at most; without free-reporter and cargo-dependence controls it does not establish the full delivery chain. Without receptor or guidance controls, a "targeted" claim is limited to observed distribution, not selective targeting.

## Functional validation and biological response

- Applicable claims: therapeutic effect, penetration, retention, thermal or immune effects, safety, degradation or clearance, and any clinical-usability claim.
- Evidence to check: in vitro uptake and viability versus in vivo efficacy, and two-dimensional culture versus three-dimensional penetration and tissue-level delivery; route, dose or dosimetry, circulation, biodistribution, and target accumulation at the claimed time point; therapeutic endpoints tied to the proposed mechanism; matched controls (free cargo at the same dose, vehicle, inactive or non-propelled robot, and a relevant standard of care where available); direct measurement of the claimed function rather than a downstream outcome; for combination claims, isolated robot, cargo, and stimulus arms; immune response, protein corona, clearance organs, and acute versus chronic toxicity where the paper claims safety or translation; "biodegradable" or "clearable" claims need degradation and clearance tracking, not composition alone.
- If missing: 2D cell death limits tumour-efficacy claims; a downstream outcome alone limits mechanism claims; without isolated arms a combination effect is not yet synergy. Keep claims at the stage the data support.
- Translation distance: distinguish the authors' stated clinical potential from demonstrated clinical usability. Large-animal models, pharmacokinetics, scalable manufacturing, and regulatory considerations describe the remaining translation distance; they are not mandatory completion items for every proof-of-concept paper, and early-stage work is not deficient for lacking them.

## Characterization by system size, dispersion, and mechanism

Select characterization by the system's size, dispersion state, and actuation mechanism; do not apply one universal panel.

- Size and dispersion: electron microscopy for size and morphology; light scattering or DLS where the size range is suitable. Micro-scale devices are not deficient merely for lacking DLS. Surface charge, composition, crystallinity, magnetic and optical properties, and stability in biological media apply as the system and claim require.
- Actuation-specific: magnetic systems — magnetization, field response, and hysteresis where relevant; acoustic systems — pressure and frequency calibration, heating; optical systems — power, wavelength, and heating; catalytic systems — fuel dependence, product inhibition, and whether the fuel is present at a relevant concentration in the biological setting; biohybrid systems — carrier viability and payload retention.
- Dosimetry: particle concentration, cargo loading, administered dose, and the method used to quantify each (for example ICP-MS, fluorescence, UV-visible absorbance), when dose-dependent claims are made.
- Safety: hemolysis, cytotoxicity, immunogenicity, and organ histology at relevant doses and time points, when safety or translation is claimed.
- If a characterization is absent: name the specific claim it limits; do not issue a generic "characterization insufficient" verdict.

## Evidence calibration

- Propulsion in buffer is not propulsion in vivo; accumulation is not penetration; uptake is not delivery; signal change is not localization; 2D cell death is not tumour efficacy.
- Remote actuation in tissue must account for attenuation, heating, and limited penetration depth of the applied field.
- Efficacy at one time point does not establish a durable response; safety in one model does not establish clinical safety.
- Claims about clinical usability require evidence at that stage; early proof-of-concept claims should stay at their actual stage.

## Common overclaims

- "targeted delivery" without ligand dependence or tissue-level colocalization;
- "in vivo navigation" inferred from static accumulation or one imaging time point;
- "biodegradable" or "clearable" inferred from composition or a single histology time point;
- "deep tissue penetration" inferred from whole-tumour homogenate signal;
- "remote control" without evidence that the field reaches the target site;
- "synergy" from a combination without isolated component arms;
- "autonomous" motion that is actually external field guidance or passive transport;
- a designed component role stated as a validated function without control or functional evidence.
