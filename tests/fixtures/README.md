# Fixtures

One JSON file per device, each a serialised `DeviceProfile` plus the expected
result:

```json
{
  "expected_class": "Class IIa",
  "expected_rule": "s2-5.2",
  "artg_reference": "123456",
  "profile": { }
}
```

Target thirty before writing rule code. Pick devices already on the ARTG so the
expected value comes from the register, not from judgement.
