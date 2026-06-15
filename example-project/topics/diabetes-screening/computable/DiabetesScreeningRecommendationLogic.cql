library DiabetesScreeningRecommendationLogic version '0.1.0'

using FHIR version '4.0.1'

include FHIRHelpers version '4.0.1' called FHIRHelpers

valueset "Prediabetes": 'http://example.org/fhir/ValueSet/prediabetes'
valueset "Type2DiabetesMellitus": 'http://example.org/fhir/ValueSet/type-2-diabetes-mellitus'
valueset "Hypertension": 'http://example.org/fhir/ValueSet/hypertension'
valueset "Obesity": 'http://example.org/fhir/ValueSet/obesity'
valueset "Overweight": 'http://example.org/fhir/ValueSet/overweight'
valueset "PolycysticOvarySyndrome": 'http://example.org/fhir/ValueSet/polycystic-ovary-syndrome'
valueset "HumanImmunodeficiencyVirusInfection": 'http://example.org/fhir/ValueSet/human-immunodeficiency-virus-infection'

parameter IsPregnant Boolean default false
parameter FastingPlasmaGlucoseMgPerdL Decimal default null
parameter TwoHourOgttGlucoseMgPerdL Decimal default null
parameter HemoglobinA1cPercent Decimal default null
parameter RandomPlasmaGlucoseMgPerdL Decimal default null
parameter HasClassicHyperglycemiaSymptoms Boolean default false

context Patient

define "Age35YearsOrOlder":
  AgeInYears() >= 35

define "HasHypertension":
  exists([Condition: "Hypertension"])

define "HasOverweight":
  exists([Condition: "Overweight"])

define "HasObesity":
  exists([Condition: "Obesity"])

define "HasPolycysticOvarySyndrome":
  exists([Condition: "PolycysticOvarySyndrome"])

define "HasHumanImmunodeficiencyVirusInfection":
  exists([Condition: "HumanImmunodeficiencyVirusInfection"])

define "HasPrediabetesHistory":
  exists([Condition: "Prediabetes"])

define "OverweightOrObesityPresent":
  "HasOverweight"
    or "HasObesity"

define "AtLeastOneAdditionalDiabetesRiskFactorPresent":
  "HasHypertension"
    or "HasPolycysticOvarySyndrome"
    or "HasHumanImmunodeficiencyVirusInfection"
    or "HasPrediabetesHistory"

define "PregnancyPresent":
  Coalesce(IsPregnant, false)

define "HasAnyScreeningResult":
  FastingPlasmaGlucoseMgPerdL is not null
    or TwoHourOgttGlucoseMgPerdL is not null
    or HemoglobinA1cPercent is not null
    or RandomPlasmaGlucoseMgPerdL is not null

define "FastingGlucoseInDiabetesRange":
  FastingPlasmaGlucoseMgPerdL is not null
    and FastingPlasmaGlucoseMgPerdL >= 126.0

define "TwoHourOgttInDiabetesRange":
  TwoHourOgttGlucoseMgPerdL is not null
    and TwoHourOgttGlucoseMgPerdL >= 200.0

define "HemoglobinA1cInDiabetesRange":
  HemoglobinA1cPercent is not null
    and HemoglobinA1cPercent >= 6.5

define "RandomGlucoseInDiabetesRange":
  RandomPlasmaGlucoseMgPerdL is not null
    and RandomPlasmaGlucoseMgPerdL >= 200.0
    and Coalesce(HasClassicHyperglycemiaSymptoms, false)

define "DiabetesDiagnosticThresholdMet":
  "FastingGlucoseInDiabetesRange"
    or "TwoHourOgttInDiabetesRange"
    or "HemoglobinA1cInDiabetesRange"
    or "RandomGlucoseInDiabetesRange"

define "FastingGlucoseInPrediabetesRange":
  FastingPlasmaGlucoseMgPerdL is not null
    and FastingPlasmaGlucoseMgPerdL >= 100.0
    and FastingPlasmaGlucoseMgPerdL <= 125.0

define "TwoHourOgttInPrediabetesRange":
  TwoHourOgttGlucoseMgPerdL is not null
    and TwoHourOgttGlucoseMgPerdL >= 140.0
    and TwoHourOgttGlucoseMgPerdL <= 199.0

define "HemoglobinA1cInPrediabetesRange":
  HemoglobinA1cPercent is not null
    and HemoglobinA1cPercent >= 5.7
    and HemoglobinA1cPercent <= 6.4

define "PrediabetesThresholdMet":
  not "DiabetesDiagnosticThresholdMet"
    and (
      "FastingGlucoseInPrediabetesRange"
        or "TwoHourOgttInPrediabetesRange"
        or "HemoglobinA1cInPrediabetesRange"
    )

define "ScreeningResultNormal":
  "HasAnyScreeningResult"
    and not "DiabetesDiagnosticThresholdMet"
    and not "PrediabetesThresholdMet"
