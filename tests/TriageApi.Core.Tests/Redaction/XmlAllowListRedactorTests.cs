using TriageApi.Core.Redaction;
using Xunit;

namespace TriageApi.Core.Tests.Redaction;

public class XmlAllowListRedactorTests
{
    private readonly XmlAllowListRedactor _redactor = new();

    [Fact]
    public void Redact_MasksLeafValuesNotOnAllowList()
    {
        var xml = "<Customer><FirstName>Jane</FirstName><Phone>5551234567</Phone></Customer>";

        var result = _redactor.Redact(xml);

        Assert.True(result.Success);
        Assert.Contains("<FirstName>[REDACTED]</FirstName>", result.RedactedXml);
        Assert.Contains("<Phone>[REDACTED]</Phone>", result.RedactedXml);
        Assert.DoesNotContain("Jane", result.RedactedXml);
        Assert.DoesNotContain("5551234567", result.RedactedXml);
    }

    [Fact]
    public void Redact_PassesThroughAllowListedElementValues()
    {
        // crtId/tinTypCde are confirmed-safe diagnostic fields from the real OXCU054 sample.
        var xml = "<OXCU054><crtId>HKX810285</crtId><tinTypCde>SSN</tinTypCde><Secret>abc123</Secret></OXCU054>";

        var result = _redactor.Redact(xml);

        Assert.True(result.Success);
        Assert.Contains("<crtId>HKX810285</crtId>", result.RedactedXml);
        Assert.Contains("<tinTypCde>SSN</tinTypCde>", result.RedactedXml);
        Assert.Contains("<Secret>[REDACTED]</Secret>", result.RedactedXml);
    }

    [Fact]
    public void Redact_RealOxcu054Sample_MasksPiiKeepsDiagnosticFields()
    {
        const string xml = """
            <?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <OXCU054>
                <header>
                    <crtId>HKX810285</crtId>
                    <crtTmstp>20260218011224338032</crtTmstp>
                    <actyCtxt>
                        <correlId>E242431B-8B79-0982-00C4-E5F2F6E3FAD6</correlId>
                        <athzCustNbr>395769222219117</athzCustNbr>
                    </actyCtxt>
                </header>
                <body>
                    <custId>00999BODIN1K4.00001</custId>
                    <custNbr>395769222219117</custNbr>
                    <tinTypCde>SSN</tinTypCde>
                    <tin>666481501</tin>
                    <tinVldCde>OK</tinVldCde>
                    <fullNme>KEITH BODINE</fullNme>
                    <chgTypCde>ADD</chgTypCde>
                    <newPhoneNbr>4377290704</newPhoneNbr>
                    <newRawPhoneNbr>4377290704</newRawPhoneNbr>
                </body>
            </OXCU054>
            """;

        var result = _redactor.Redact(xml);

        Assert.True(result.Success);

        // PII must be masked.
        Assert.DoesNotContain("666481501", result.RedactedXml);
        Assert.DoesNotContain("KEITH BODINE", result.RedactedXml);
        Assert.DoesNotContain("00999BODIN1K4.00001", result.RedactedXml);
        Assert.DoesNotContain("4377290704", result.RedactedXml);

        // Confirmed-safe diagnostic fields pass through.
        Assert.Contains("<crtId>HKX810285</crtId>", result.RedactedXml);
        Assert.Contains("<correlId>E242431B-8B79-0982-00C4-E5F2F6E3FAD6</correlId>", result.RedactedXml);
        Assert.Contains("<athzCustNbr>395769222219117</athzCustNbr>", result.RedactedXml);
        Assert.Contains("<tinTypCde>SSN</tinTypCde>", result.RedactedXml);
        Assert.Contains("<tinVldCde>OK</tinVldCde>", result.RedactedXml);
        Assert.Contains("<chgTypCde>ADD</chgTypCde>", result.RedactedXml);
    }

    [Fact]
    public void Redact_PreservesElementStructureAndCounts()
    {
        var xml = "<Root><Item>a</Item><Item>b</Item><Item>c</Item></Root>";

        var result = _redactor.Redact(xml);

        Assert.True(result.Success);
        var itemCount = System.Text.RegularExpressions.Regex.Matches(result.RedactedXml!, "<Item>").Count;
        Assert.Equal(3, itemCount);
    }

    [Fact]
    public void Redact_MasksAttributeValuesNotOnAllowList()
    {
        var xml = "<Customer ssn=\"123-45-6789\"><Name>Jane</Name></Customer>";

        var result = _redactor.Redact(xml);

        Assert.True(result.Success);
        Assert.DoesNotContain("123-45-6789", result.RedactedXml);
    }

    [Fact]
    public void Redact_PreservesNamespaceDeclarations()
    {
        var xml = "<Customer xmlns:x=\"urn:example\"><x:Name>Jane</x:Name></Customer>";

        var result = _redactor.Redact(xml);

        Assert.True(result.Success);
        Assert.Contains("xmlns:x=\"urn:example\"", result.RedactedXml);
        Assert.DoesNotContain("Jane", result.RedactedXml);
    }

    [Theory]
    [InlineData("<Unclosed><Tag></Unclosed>")]
    [InlineData("not xml at all")]
    [InlineData("<Root>&invalidEntity;</Root>")]
    public void Redact_BlocksMalformedXml_DoesNotPassThroughRaw(string malformed)
    {
        var result = _redactor.Redact(malformed);

        Assert.False(result.Success);
        Assert.Null(result.RedactedXml);
        Assert.NotNull(result.BlockReason);
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("   ")]
    public void Redact_NullOrWhitespaceInput_ReturnsEmptyOk(string? input)
    {
        var result = _redactor.Redact(input);

        Assert.True(result.Success);
        Assert.Equal(string.Empty, result.RedactedXml);
    }

    [Fact]
    public void Redact_DeeplyNestedStructure_EveryLeafMaskedByDefault()
    {
        var xml = "<A><B><C><D>secret-value</D></C></B></A>";

        var result = _redactor.Redact(xml);

        Assert.True(result.Success);
        Assert.DoesNotContain("secret-value", result.RedactedXml);
        Assert.Contains("<D>[REDACTED]</D>", result.RedactedXml);
    }
}
