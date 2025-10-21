"""
Quick test of the player parser
"""
from player_parser import parse_height_to_inches, parse_weight_to_pounds, parse_birth_date

# Test height parsing
print("Testing height parsing:")
print(f"  '6-2' -> {parse_height_to_inches('6-2')} inches (expected 74)")
print(f"  '5-11' -> {parse_height_to_inches('5-11')} inches (expected 71)")
print(f"  '6-0' -> {parse_height_to_inches('6-0')} inches (expected 72)")
print(f"  None -> {parse_height_to_inches(None)} (expected None)")

# Test weight parsing
print("\nTesting weight parsing:")
print(f"  '200' -> {parse_weight_to_pounds('200')} lbs (expected 200)")
print(f"  '185' -> {parse_weight_to_pounds('185')} lbs (expected 185)")
print(f"  '235 lbs' -> {parse_weight_to_pounds('235 lbs')} lbs (expected 235)")
print(f"  None -> {parse_weight_to_pounds(None)} (expected None)")

# Test birth date parsing
print("\nTesting birth date parsing:")
print(f"  '1998-05-15' -> {parse_birth_date('1998-05-15')} (expected 1998-05-15)")
print(f"  '1998-05-15T00:00:00Z' -> {parse_birth_date('1998-05-15T00:00:00Z')} (expected 1998-05-15)")
print(f"  None -> {parse_birth_date(None)} (expected None)")

print("\n✓ All tests complete!")
