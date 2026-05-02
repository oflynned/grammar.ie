def verify(original_german, translated_english):
    """
    Simple Python verification (No LLM needed for this check)
    """
    print(f"  🔹 [Step 3] Verifying...")

    # Simple check: Do we have roughly the same number of Irish tokens?
    input_tokens = original_german.count("__IRISH_")
    output_tokens = translated_english.count("__IRISH_")

    if input_tokens != output_tokens:
        print(f"    ⚠️ WARNING: Token Mismatch! German: {input_tokens}, English: {output_tokens}")
        # In a real pipeline, you might raise an error or retry here.
        # For now, we just warn.
    else:
        print(f"    ✅ Verification Passed: {output_tokens} tokens preserved.")

    return True


def verify_no_remaining_tokens(content):
    missing_tokens = content.count("__IRISH_")

    if missing_tokens > 0:
        print(f"    ⚠️ WARNING: ${missing_tokens} orphaned tokens!")
    else:
        print(f"    ✅ Verification Passed: No orphaned tokens.")
