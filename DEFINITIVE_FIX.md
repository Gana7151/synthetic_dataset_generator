# Definitive Fix: Blank Form PDF + Clean Overlay Pipeline
### Root Cause Confirmed from Uploaded PDF — April 2026

---

## What You're Actually Seeing (The Real Problem)

Looking at the uploaded `test_output_variant_001.pdf` directly, every page shows **two complete datasets simultaneously** — Johnson *and* Smith values stacked on top of each other. This is not a coordinate offset issue. This is a **source architecture failure**.

```
Current broken flow:
  johnson_source.pdf  ←── pre-filled with Johnson data (printed into page stream)
       +
  smith_overlay.xml   ←── synthetic Smith data rendered on top
       =
  output.pdf          ←── BOTH datasets visible, neither erasable
```

The source PDF `2024_Tax_Return_Documents_(JOHNSON_JOHN_and_EMILY).pdf` has Johnson's data **baked into the PDF content stream** as drawn text, not as AcroForm fields. You cannot clear it with any field-reset API. Every overlay you apply just adds a second layer of text on top.

**The fix is not a patch. It's a pipeline change.**

---

## The Correct Architecture

```
New correct flow:

STEP 1: Generate blank_form.pdf  (one-time, run once)
  johnson_source.pdf
  + white-out boxes over every data position
  = blank_form.pdf     ←── clean form structure, zero Johnson data visible

STEP 2: Generate synthetic XML (per record)
  blank_template.xml   ←── empty structural template
  + quant model values injected by generate_variation()
  = synthetic_N.xml

STEP 3: Overlay (per record)
  blank_form.pdf + synthetic_N.xml → output_N.pdf  ✓ clean, no overlap
```

Run Step 1 once. Commit `blank_form.pdf` to the repo. Steps 2 and 3 run per synthetic record.

---

## Step 1 — Generate blank_form.pdf

Add this function to `generate_tax_pdf.py`. It reads the source PDF and draws white rectangles over every coordinate listed in `FIELD_DEFINITIONS` plus the address/header zones identified by pdfplumber.

```python
def generate_blank_form(source_pdf: str, output_path: str):
    """
    Creates a blank form PDF by white-boxing every data field position
    defined in FIELD_DEFINITIONS and CHECKBOX_DEFINITIONS.
    Run this ONCE to produce blank_form.pdf.
    """
    from pypdf import PdfReader, PdfWriter
    import io
    from reportlab.pdfgen import canvas

    reader = PdfReader(source_pdf)
    writer = PdfWriter()

    # Build page → list of (x0, top, x1, bottom) white-out boxes
    # Derived from FIELD_DEFINITIONS + ADDITIONAL_BLANK_ZONES
    blank_zones: dict[int, list] = {}

    # 1. Every field in FIELD_DEFINITIONS gets a white-out box
    #    Box = 4pt wider than font_size tall, 150pt wide right-aligned from x
    for (page, xpath, x, top, font_size, formatter) in FIELD_DEFINITIONS:
        pad = 2
        box = (x - pad, top - pad, x + 150, top + font_size + pad)
        blank_zones.setdefault(page, []).append(box)

    # 2. Additional zones not in FIELD_DEFINITIONS:
    #    Header name/SSN rows, address blocks, preparer info, checkboxes
    ADDITIONAL_BLANK_ZONES = {
        # Page 1 — filer name/SSN header + address block + dependents
        1: [
            (36.0,  88.0, 470.0, 102.0),   # primary name
            (36.0, 112.0, 470.0, 126.0),   # spouse name
            (36.0, 137.0, 580.0, 150.0),   # address
            (36.0, 160.0, 430.0, 174.0),   # city/state/zip
            (87.0, 375.0, 510.0, 405.0),   # dependents row 1 + 2
            (440.0, 730.0, 590.0, 744.0),  # filing status area
        ],
        # Page 2 — name/SSN header + occupation + email/phone + preparer block
        2: [
            (115.0, 22.0, 470.0, 40.0),    # name + SSN in header
            (285.0, 549.0, 580.0, 563.0),  # occupation fields
            (285.0, 563.0, 580.0, 577.0),  # spouse occupation
            (36.0,  577.0, 580.0, 592.0),  # phone + email
            (36.0,  668.0, 580.0, 780.0),  # preparer block
        ],
        # Page 7 — Schedule B name/SSN row + payer names/amounts
        7: [
            (36.0,  70.0, 545.0,  85.0),   # name + SSN
            (36.0, 142.0, 580.0, 162.0),   # interest payer name
            (36.0, 324.0, 580.0, 344.0),   # dividend payer name
        ],
        # Page 8 — Schedule C header (name, SSN, business info)
        8: [
            (36.0,  94.0, 545.0, 110.0),   # proprietor name + SSN
            (36.0, 112.0, 545.0, 126.0),   # business description
            (36.0, 124.0, 545.0, 136.0),   # business name
            (36.0, 136.0, 545.0, 150.0),   # business address
        ],
        # Page 9 — Schedule C Part V other expenses descriptions
        9: [
            (36.0, 460.0, 580.0, 510.0),   # expense description rows
        ],
        # Page 10 — Schedule SE name/SSN
        10: [(36.0, 94.0, 558.0, 108.0)],
        # Page 11 — Schedule 8812 name/SSN
        11: [(36.0, 105.0, 540.0, 120.0)],
        # Page 12 — Schedule 8812 p2 header
        12: [(150.0, 35.0, 545.0, 52.0)],
        # Page 13 — Form 8995 taxpayer name + business name row
        13: [
            (36.0, 94.0, 545.0, 108.0),
            (36.0, 140.0, 545.0, 156.0),
        ],
        # Page 14 — Form 8867 name/SSN + preparer
        14: [
            (36.0, 106.0, 510.0, 120.0),
            (36.0, 126.0, 510.0, 140.0),
            (60.0, 480.0, 580.0, 495.0),
        ],
        # Page 15 — Form 8867 p2 header
        15: [(120.0, 35.0, 510.0, 52.0)],
        # Page 16 — Form 4562 name/SSN + business name
        16: [
            (36.0, 88.0, 545.0, 103.0),
            (36.0, 103.0, 545.0, 118.0),
        ],
        # Page 17 — Form 4562 p2 header + vehicle info
        17: [
            (115.0, 22.0, 502.0, 40.0),
            (36.0, 175.0, 580.0, 195.0),
        ],
        # Pages 18–22 — 1040-V and 1040-ES vouchers: full data block
        18: [(36.0, 55.0, 580.0, 780.0)],
        19: [(36.0, 55.0, 580.0, 780.0)],
        20: [(36.0, 55.0, 580.0, 780.0)],
        21: [(36.0, 55.0, 580.0, 780.0)],
        22: [(36.0, 55.0, 580.0, 780.0)],
        # Page 23 — CA 540 p1 header + address block + exemption checkboxes
        23: [
            (33.0,  91.0, 500.0, 106.0),
            (33.0, 104.0, 580.0, 175.0),
        ],
        # Pages 24–28 — CA 540 continuation headers
        24: [(36.0, 43.0, 580.0, 135.0)],
        25: [(36.0, 43.0, 580.0,  70.0)],
        26: [(36.0, 43.0, 580.0,  70.0)],
        27: [(36.0, 43.0, 580.0,  70.0)],
        28: [(36.0, 43.0, 580.0, 200.0)],
    }

    for page_num, zones in ADDITIONAL_BLANK_ZONES.items():
        blank_zones.setdefault(page_num, []).extend(zones)

    for i, source_page in enumerate(reader.pages):
        page_num = i + 1
        pw = float(source_page.mediabox.width)
        ph = float(source_page.mediabox.height)

        zones = blank_zones.get(page_num, [])
        if zones:
            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=(pw, ph))
            c.setFillColorRGB(1, 1, 1)
            for (x0, top, x1, bot) in zones:
                rl_y = ph - bot
                c.rect(x0, rl_y, x1 - x0, bot - top, fill=1, stroke=0)
            c.save()
            buf.seek(0)
            from pypdf import PdfReader as _R
            overlay = _R(buf).pages[0]
            source_page.merge_page(overlay)

        writer.add_page(source_page)

    with open(output_path, "wb") as f:
        writer.write(f)
    print(f"Blank form written: {output_path}")
```

**CLI hook — add to `main()`:**
```python
parser.add_argument("--make-blank", action="store_true",
                    help="Generate blank_form.pdf from source PDF and exit")

if args.make_blank:
    generate_blank_form(args.source, "blank_form.pdf")
    sys.exit(0)
```

**Run it:**
```bash
python generate_tax_pdf.py \
  --source "2024_Tax_Return_Documents_(JOHNSON_JOHN_and_EMILY).pdf" \
  --xml dummy.xml \
  --out /dev/null \
  --make-blank
```

This produces `blank_form.pdf`. **Commit it.** Never regenerate unless the source template changes.

---

## Step 2 — Blank XML Template

The generator currently mutates the Johnson XML in-place. That means any XPath not explicitly overwritten by `generate_variation()` retains Johnson's original value — which then gets overlaid as a second data source.

Create `blank_template.xml` — every data field present in the XML but with zeroed/empty values. `generate_variation()` starts from this template instead of the Johnson XML.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Return returnVersion="2024v1.0">

  <ReturnHeader binaryAttachmentCnt="0">
    <ReturnTs>2025-04-15T00:00:00Z</ReturnTs>
    <TaxYr>2024</TaxYr>
    <TaxPeriodBeginDt>2024-01-01</TaxPeriodBeginDt>
    <TaxPeriodEndDt>2024-12-31</TaxPeriodEndDt>

    <SelfSelectPINGrp>
      <PrimaryBirthDt></PrimaryBirthDt>
      <SpouseBirthDt></SpouseBirthDt>
      <PrimaryPriorYearAGIAmt>0</PrimaryPriorYearAGIAmt>
    </SelfSelectPINGrp>

    <Filer>
      <PrimarySSN></PrimarySSN>
      <SpouseSSN></SpouseSSN>
      <NameLine1Txt></NameLine1Txt>
      <SpouseNameLine1Txt></SpouseNameLine1Txt>
      <PhoneNum></PhoneNum>
      <EmailAddressTxt></EmailAddressTxt>
      <USAddress>
        <AddressLine1Txt></AddressLine1Txt>
        <CityNm></CityNm>
        <StateAbbreviationCd></StateAbbreviationCd>
        <ZIPCd></ZIPCd>
      </USAddress>
    </Filer>
  </ReturnHeader>

  <ReturnData documentCnt="10">

    <!-- Form 1040 -->
    <IRS1040 documentId="IRS1040-1">
      <IndividualReturnFilingStatusCd>2</IndividualReturnFilingStatusCd>
      <VirtualCurAcquiredDurTYInd>false</VirtualCurAcquiredDurTYInd>

      <!-- Dependents -->
      <DependentDetail>
        <DependentFirstNm></DependentFirstNm>
        <DependentLastNm></DependentLastNm>
        <DependentSSN></DependentSSN>
        <DependentRelationshipCd></DependentRelationshipCd>
        <EligibleForChildTaxCreditInd></EligibleForChildTaxCreditInd>
      </DependentDetail>
      <DependentDetail>
        <DependentFirstNm></DependentFirstNm>
        <DependentLastNm></DependentLastNm>
        <DependentSSN></DependentSSN>
        <DependentRelationshipCd></DependentRelationshipCd>
        <EligibleForChildTaxCreditInd></EligibleForChildTaxCreditInd>
      </DependentDetail>

      <!-- Income -->
      <WagesAmt>0</WagesAmt>
      <WagesSalariesAndTipsAmt>0</WagesSalariesAndTipsAmt>
      <TaxExemptInterestAmt>0</TaxExemptInterestAmt>
      <TaxableInterestAmt>0</TaxableInterestAmt>
      <OrdinaryDividendsAmt>0</OrdinaryDividendsAmt>
      <QualifiedDividendsAmt>0</QualifiedDividendsAmt>
      <BusinessIncomeAmt>0</BusinessIncomeAmt>
      <TotalIncomeAmt>0</TotalIncomeAmt>
      <AdjustmentsToIncomeAmt>0</AdjustmentsToIncomeAmt>
      <AdjustedGrossIncomeAmt>0</AdjustedGrossIncomeAmt>

      <!-- Deductions -->
      <TotalItemizedOrStandardDedAmt>0</TotalItemizedOrStandardDedAmt>
      <QualifiedBusinessIncomeDedAmt>0</QualifiedBusinessIncomeDedAmt>
      <TotalDeductionsAmt>0</TotalDeductionsAmt>
      <TaxableIncomeAmt>0</TaxableIncomeAmt>

      <!-- Tax and Credits -->
      <TaxAmt>0</TaxAmt>
      <TotalTaxBeforeCrAndOthTaxesAmt>0</TotalTaxBeforeCrAndOthTaxesAmt>
      <ChildTaxCreditAmt>0</ChildTaxCreditAmt>
      <TotalCreditsAmt>0</TotalCreditsAmt>
      <TaxLessCreditsAmt>0</TaxLessCreditsAmt>
      <OtherTaxesAmt>0</OtherTaxesAmt>
      <TotalTaxAmt>0</TotalTaxAmt>

      <!-- Payments -->
      <FormW2WithheldTaxAmt>0</FormW2WithheldTaxAmt>
      <WithholdingTaxAmt>0</WithholdingTaxAmt>
      <TotalPaymentsAmt>0</TotalPaymentsAmt>
      <OverpaidAmt>0</OverpaidAmt>
      <RefundAmt>0</RefundAmt>
      <AmountOwedAmt>0</AmountOwedAmt>
    </IRS1040>

    <!-- W-2 -->
    <IRSW2 documentId="IRSW2-0">
      <EmployeeSSN></EmployeeSSN>
      <EmployerEIN></EmployerEIN>
      <EmployerName><BusinessNameLine1Txt></BusinessNameLine1Txt></EmployerName>
      <EmployeeNm></EmployeeNm>
      <WagesAmt>0</WagesAmt>
      <WithholdingAmt>0</WithholdingAmt>
      <SocialSecurityWagesAmt>0</SocialSecurityWagesAmt>
      <SocialSecurityTaxAmt>0</SocialSecurityTaxAmt>
      <MedicareWagesAndTipsAmt>0</MedicareWagesAndTipsAmt>
      <MedicareTaxWithheldAmt>0</MedicareTaxWithheldAmt>
      <EmployeeOccupation></EmployeeOccupation>
      <SpouseOccupation></SpouseOccupation>
    </IRSW2>

    <!-- Schedule 1 -->
    <IRS1040Schedule1 documentId="Sch1-1">
      <AdditionalIncomeAmt>0</AdditionalIncomeAmt>
      <AdjustmentsToIncomeAmt>0</AdjustmentsToIncomeAmt>
    </IRS1040Schedule1>

    <!-- Schedule 2 -->
    <IRS1040Schedule2 documentId="Sch2-1">
      <AlternativeMinimumTaxAmt>0</AlternativeMinimumTaxAmt>
      <TotalAdditionalTaxAmt>0</TotalAdditionalTaxAmt>
      <SelfEmploymentTaxAmt>0</SelfEmploymentTaxAmt>
      <TotalOtherTaxesAmt>0</TotalOtherTaxesAmt>
    </IRS1040Schedule2>

    <!-- Schedule B -->
    <IRS1040ScheduleB documentId="SchB-1">
      <InterestPayerName></InterestPayerName>
      <InterestAmt>0</InterestAmt>
      <TotalInterestAmt>0</TotalInterestAmt>
      <DividendPayerName></DividendPayerName>
      <OrdinaryDividendsAmt>0</OrdinaryDividendsAmt>
      <TotalOrdinaryDividendsAmt>0</TotalOrdinaryDividendsAmt>
    </IRS1040ScheduleB>

    <!-- Schedule C -->
    <IRS1040ScheduleC documentId="SchC-1">
      <ProprietorNm></ProprietorNm>
      <PrincipalBusinessActivityDesc></PrincipalBusinessActivityDesc>
      <PrincipalBusinessActivityCd></PrincipalBusinessActivityCd>
      <BusinessName><BusinessNameLine1Txt></BusinessNameLine1Txt></BusinessName>
      <BusinessAddressTxt></BusinessAddressTxt>
      <GrossReceiptsOrSalesAmt>0</GrossReceiptsOrSalesAmt>
      <TotalGrossReceiptsAmt>0</TotalGrossReceiptsAmt>
      <AdvertisingAmt>0</AdvertisingAmt>
      <DepreciationAmt>0</DepreciationAmt>
      <OfficeExpensesAmt>0</OfficeExpensesAmt>
      <RentLeaseAmt>0</RentLeaseAmt>
      <SuppliesAmt>0</SuppliesAmt>
      <TaxesAndLicensesAmt>0</TaxesAndLicensesAmt>
      <MealsAmt>0</MealsAmt>
      <OtherBusinessExpensesAmt>0</OtherBusinessExpensesAmt>
      <TotalExpensesAmt>0</TotalExpensesAmt>
      <NetProfitOrLossAmt>0</NetProfitOrLossAmt>
      <Part5_OtherExpenses>
        <Item seq="1"><Description></Description><Amount>0</Amount></Item>
        <Item seq="2"><Description></Description><Amount>0</Amount></Item>
        <Item seq="3"><Description></Description><Amount>0</Amount></Item>
        <L48_TotalOtherExpenses>0</L48_TotalOtherExpenses>
      </Part5_OtherExpenses>
    </IRS1040ScheduleC>

    <!-- Schedule SE -->
    <IRS1040ScheduleSE documentId="SchSE-1">
      <NetProfitOrLossAmt>0</NetProfitOrLossAmt>
      <SETotalNetEarningsOrLossAmt>0</SETotalNetEarningsOrLossAmt>
      <L4a_Multiply_9235>0</L4a_Multiply_9235>
      <L4c_Combined>0</L4c_Combined>
      <L6_AddLines4c5b>0</L6_AddLines4c5b>
      <L9_Subtract8dFrom7>0</L9_Subtract8dFrom7>
      <L10_Multiply_124>0</L10_Multiply_124>
      <L11_Multiply_029>0</L11_Multiply_029>
      <SelfEmploymentTaxAmt>0</SelfEmploymentTaxAmt>
      <DeductibleSelfEmploymentTaxAmt>0</DeductibleSelfEmploymentTaxAmt>
    </IRS1040ScheduleSE>

    <!-- Schedule 8812 -->
    <IRS1040Schedule8812 documentId="Sch8812-1">
      <L1_AGI>0</L1_AGI>
      <L3_AddLines1_2d>0</L3_AddLines1_2d>
      <L4_QualifyingChildrenUnder17>0</L4_QualifyingChildrenUnder17>
      <L5_Multiply2000>0</L5_Multiply2000>
      <L6_OtherDependents>0</L6_OtherDependents>
      <L7_Multiply500>0</L7_Multiply500>
      <L8_AddLines5_7>0</L8_AddLines5_7>
      <L12_CreditAfterPhaseout>0</L12_CreditAfterPhaseout>
      <L13_CreditLimitWorksheetA>0</L13_CreditLimitWorksheetA>
      <ChildTaxCreditAmt>0</ChildTaxCreditAmt>
      <L16a_NumKidsX1700>0</L16a_NumKidsX1700>
      <L16b_EarnedIncome>0</L16b_EarnedIncome>
      <L17_SmallerOf16a16b>0</L17_SmallerOf16a16b>
      <L18a_EarnedIncome>0</L18a_EarnedIncome>
      <L19_Subtract2500>0</L19_Subtract2500>
      <L20_Multiply15pct>0</L20_Multiply15pct>
      <L27_AdditionalChildTaxCredit>0</L27_AdditionalChildTaxCredit>
    </IRS1040Schedule8812>

    <!-- Form 8995 -->
    <IRS8995 documentId="8995-1">
      <QBITrades>
        <Trade seq="1">
          <n></n>
          <TaxpayerID></TaxpayerID>
          <QBIAmount>0</QBIAmount>
        </Trade>
      </QBITrades>
      <L2_TotalQBI>0</L2_TotalQBI>
      <L4_TotalQBIAfterCarryforward>0</L4_TotalQBIAfterCarryforward>
      <L5_QBIComponent_20pct>0</L5_QBIComponent_20pct>
      <L10_QBIDeductionBeforeLimit>0</L10_QBIDeductionBeforeLimit>
      <L11_TaxableIncomeBeforeQBI>0</L11_TaxableIncomeBeforeQBI>
      <L13_L11MinusL12>0</L13_L11MinusL12>
      <L14_IncomeLimitation>0</L14_IncomeLimitation>
      <L15_QBIDeduction>0</L15_QBIDeduction>
    </IRS8995>

    <!-- Form 4562 -->
    <IRS4562 documentId="4562-1">
      <Section179ExpenseAmt>0</Section179ExpenseAmt>
      <DepreciationAmt>0</DepreciationAmt>
      <TotalDepreciationAmt>0</TotalDepreciationAmt>
      <L28_TotalListedPropDep>0</L28_TotalListedPropDep>
      <L30_BusinessMiles>0</L30_BusinessMiles>
      <L31_CommutingMiles>0</L31_CommutingMiles>
      <L32_OtherPersonalMiles>0</L32_OtherPersonalMiles>
      <L33_TotalMiles>0</L33_TotalMiles>
      <Vehicle seq="1">
        <Description></Description>
        <DatePlacedInService></DatePlacedInService>
        <BusinessUsePct></BusinessUsePct>
        <DepreciationAllowed>0</DepreciationAllowed>
      </Vehicle>
    </IRS4562>

    <!-- Preparer Info -->
    <PreparedBy documentId="Prep-1">
      <PreparerName></PreparerName>
      <PreparerPTIN></PreparerPTIN>
      <DocumentsReliedOn></DocumentsReliedOn>
    </PreparedBy>

    <!-- Form 1040-V -->
    <Form1040V documentId="1040V-1">
      <PrimarySSN></PrimarySSN>
      <SpouseSSN></SpouseSSN>
      <PaymentAmount>0</PaymentAmount>
      <TaxpayerName></TaxpayerName>
      <Address></Address>
      <City></City>
    </Form1040V>

    <!-- Form 1040-ES Vouchers -->
    <Form1040ES documentId="1040ES-1">
      <TaxpayerName></TaxpayerName>
      <Voucher seq="1"><Amount>0</Amount></Voucher>
      <Voucher seq="2"><Amount>0</Amount></Voucher>
      <Voucher seq="3"><Amount>0</Amount></Voucher>
      <Voucher seq="4"><Amount>0</Amount></Voucher>
    </Form1040ES>

    <!-- CA 540 -->
    <CA540 documentId="CA540-1">
      <Header>
        <PrimarySSN></PrimarySSN>
        <SpouseSSN></SpouseSSN>
        <PrimaryFirstName></PrimaryFirstName>
        <PrimaryLastName></PrimaryLastName>
        <SpouseFirstName></SpouseFirstName>
        <SpouseLastName></SpouseLastName>
        <Address></Address>
        <City></City>
        <State></State>
        <ZIP></ZIP>
      </Header>
      <Exemptions>
        <L7_PersonalExemption_Amount>0</L7_PersonalExemption_Amount>
      </Exemptions>
      <Dependents>
        <Dependent seq="1">
          <FirstName></FirstName>
          <LastName></LastName>
          <SSN></SSN>
        </Dependent>
        <Dependent seq="2">
          <FirstName></FirstName>
          <LastName></LastName>
          <SSN></SSN>
        </Dependent>
      </Dependents>
      <L11_TotalExemptionCredits>0</L11_TotalExemptionCredits>
      <TaxableIncome>
        <L12_StateWages>0</L12_StateWages>
        <L13_FederalAGI>0</L13_FederalAGI>
        <L15_AfterSubtractions>0</L15_AfterSubtractions>
        <L16_CAAdditions>0</L16_CAAdditions>
        <L17_CAAdjustedGrossIncome>0</L17_CAAdjustedGrossIncome>
        <L18_Deduction>0</L18_Deduction>
        <L19_TaxableIncome>0</L19_TaxableIncome>
      </TaxableIncome>
      <Tax>
        <L31_TaxFromTable>0</L31_TaxFromTable>
        <L32_ExemptionCredits>0</L32_ExemptionCredits>
        <L33_TaxAfterExemptionCredits>0</L33_TaxAfterExemptionCredits>
        <L35_TotalTax>0</L35_TotalTax>
      </Tax>
      <SpecialCredits>
        <L48_TaxAfterCredits>0</L48_TaxAfterCredits>
      </SpecialCredits>
      <OtherTaxes>
        <L64_TotalTax>0</L64_TotalTax>
      </OtherTaxes>
      <Payments>
        <L71_CAWithheld>0</L71_CAWithheld>
        <L78_TotalPayments>0</L78_TotalPayments>
      </Payments>
      <UseAndPenalty>
        <L93_PaymentsAfterISR>0</L93_PaymentsAfterISR>
        <L95_PaymentsBalance>0</L95_PaymentsBalance>
      </UseAndPenalty>
      <RefundOrOwed>
        <L96_OverpaidTax>0</L96_OverpaidTax>
        <L97_OverpaidTaxAvailable>0</L97_OverpaidTaxAvailable>
        <L99_RefundAvailable>0</L99_RefundAvailable>
      </RefundOrOwed>
      <AmountOwedOrRefund>
        <L115_Refund>0</L115_Refund>
      </AmountOwedOrRefund>
    </CA540>

  </ReturnData>
</Return>
```

---

## Step 3 — Fix generate_variation() to Use Blank Template

Change the function signature from loading the Johnson XML to loading `blank_template.xml`:

```python
# BEFORE (broken):
def generate_variation(xml_path: str, source_pdf: str, output_path: str, seed: int):
    root = load_xml(xml_path)   # loads johnson XML with pre-filled values

# AFTER (correct):
BLANK_TEMPLATE_PATH = Path(__file__).parent / "blank_template.xml"

def generate_variation(source_pdf: str, output_path: str, seed: int):
    root = load_xml(str(BLANK_TEMPLATE_PATH))   # always starts from blank
```

And in `main()`:
```python
# BEFORE:
for i in range(args.variations):
    generate_variation(args.xml, args.source, variant_path, seed=args.seed + i)

# AFTER:
for i in range(args.variations):
    generate_variation(args.source, variant_path, seed=args.seed + i)
```

---

## Step 4 — Fix FIELD_DEFINITIONS Coordinate Errors

These are still required regardless of the blank form approach. The coordinates control where text lands. If wrong, text lands on form label zones.

| Page | Field | Bug | Change |
|------|-------|-----|--------|
| 2 | `NameLine1Txt` | x=39.5 hits "Form" label | x → **118.3** |
| 7 | `PrimarySSN` | top=99.5 is 24pt below actual row | top → **75.5** |
| 7 | `NameLine1Txt` | **missing entirely** | add at (39.1, **75.5**) |
| 12 | `NameLine1Txt` + `PrimarySSN` | top=37.7 is 1.8pt high | top → **39.5** |
| 14 | `NameLine1Txt` + `PrimarySSN` | top=109.7 is 1.8pt high | top → **111.5** |
| 15 | `NameLine1Txt` + `PrimarySSN` | top=37.7 is 1.8pt high | top → **39.5** |
| 17 | `NameLine1Txt` + `PrimarySSN` | top=25.7 is 1.8pt high | top → **27.5** |
| 24–28 | `PrimarySSN` | x=478.3, top=27.5 is Federal coords | x → **306.0**, top → **49.1** |
| 24–28 | `NameLine1Txt` | **missing entirely** | add at (90.0, **49.1**) |

The 1.8pt offset on pages 12/14/15/17 comes from the y-formula subtracting full `font_size` instead of just the ascent. The fastest fix is correcting the hardcoded `top` values as shown above.

---

## Step 5 — Remove fmt_money from Zero-Value Fields

Currently `fmt_money("0")` returns `"0"` and gets overlaid on every field. On a blank form this means `0` appears in every dollar box — which looks wrong. Add a guard:

```python
def fmt_money(val: str) -> str:
    try:
        n = int(val)
        if n == 0:
            return ""          # don't render zero-value fields
        return f"{n:,}"
    except (ValueError, TypeError):
        return val
```

---

## Complete New Workflow

```bash
# Run once — create the blank form template
python generate_tax_pdf.py \
  --source "2024_Tax_Return_Documents_(JOHNSON_JOHN_and_EMILY).pdf" \
  --xml blank_template.xml \
  --out /dev/null \
  --make-blank

# Verify blank_form.pdf looks clean (no Johnson data visible)

# Generate 50 synthetic records using blank form as source
python generate_tax_pdf.py \
  --source blank_form.pdf \
  --xml blank_template.xml \
  --out output/batch/ \
  --variations 50 \
  --seed 42
```

---

## Implementation Order

1. **Save `blank_template.xml`** to repo root
2. **Add `generate_blank_form()`** to `generate_tax_pdf.py`
3. **Add `--make-blank` CLI flag** and run it → verify output visually
4. **Fix FIELD_DEFINITIONS** coordinates (table in Step 4)
5. **Fix `fmt_money`** to suppress zeros
6. **Update `generate_variation()`** to load from `blank_template.xml`
7. **Update CLI loop** to call `generate_variation(source_pdf, out_path, seed)`
8. **Run batch test** with `--variations 5`, open PDFs, confirm clean output

---

## Why the Previous White-Out Approach Was Incomplete

The first guide (Part 3 of `PDF_FIX_MASTER.md`) identified the right mechanism but applied it **per-generation**. This means:

- White-out boxes get drawn on every PDF generation call
- You're rendering ~400 white rectangles per PDF on top of Johnson's pre-printed data
- It works, but it's wasteful and fragile — if a box is slightly too small, Johnson's digit bleeds through

The blank form approach is architecturally cleaner:
- White-out happens once, to the source template
- Stored as `blank_form.pdf`
- All downstream generations overlay on a provably clean surface
- White-out precision issues are fixed once, not chased per generation

*End of fix guide.*
