# shrinky rink

# what

`shrinky-rink.py` is a tiny Python 3 script that interfaces with the [Yerba Buena Ice Skating and Bowling Center](https://goo.gl/maps/e9JHQGRhUHAYJHiJ9)'s API to quickly sign you up for figure skating freestyle sessions.

It only depends on the `requests` library. You can call it as follows:

```
python3 shrinky-rink.py [username] [password] HH:MM
```

For example:
```
python3 shrinky-rink.py test@test.com password 06:00
python3 shrinky-rink.py test@test.com password 07:45
```

# why

This is probably the most obscure project I'll ever have on my GitHub, but signing up for freestyle sessions every day using the rink's website was annoying and time-consuming.
