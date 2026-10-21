        elif key == "priority":
            if value is None:
                raise HTTPException(status_code=422, detail="priority must be one of low, medium, high")
            validate_priority(value)
