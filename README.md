# shrinky rink

# what

`shrinkyrink.py` is a tiny Python 3 script that interfaces with the [Yerba Buena Ice Skating and Bowling Center](https://goo.gl/maps/e9JHQGRhUHAYJHiJ9)'s API to quickly sign you up for figure skating freestyle sessions.

If you're calling it via the script it only requires `requests`.

You can call it as follows:

```
python3 shrinkyrink.py [username] [password] HH:MM
```

For example:
```
python3 shrinkyrink.py test@test.com password 06:00
python3 shrinkyrink.py test@test.com password 07:45
```

There is also a way for running it as an HTTP service, which is useful for connecting it to iOS's Shortcuts app. You will need `flask`.

```
FLASK_APP="server" python3 -m flask run
```

There are two routes (using [Python strftime syntax](https://strftime.org/)):
```
# Sign up for today's freestyle at this time:
/today/:username/:password/%H:%M
# Sign up for a particular date's freestyle at this time:
/date/:username/:password/%d.%m.%y/%H:%M
```

# why

This is probably the most obscure project I'll ever have on my GitHub, but signing up for freestyle sessions every day using the rink's website was annoying and time-consuming.
