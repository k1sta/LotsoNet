#!/usr/bin/env python3
"""Summon the Lotso-Terminator bear onto the machine's physical display.

Designed to be exec()'d by a root LotsoNet runner that then calls main():
there is no __file__ and no argv to rely on. Running as root, it finds the
graphical session on the monitor (seat0's active session, or $BEAR_USER),
drops privileges to that user, and opens a terminal window *on their display*
showing the ASCII art. The window just displays the bear — no shell, no
interaction; closing the window ends it.

main() is idempotent and returns a JSON-serialisable status dict.
"""
import base64
import glob
import os
import pwd
import shutil
import subprocess
import zlib

# Compressed ANSI half-block art (decompresses to the terminal-ready string).
ART_B64 = (
    "eJzNfdmxJTmO5X+rUD8jAjfnYleUlqF1qI+WoQUcScaxEgD5loyqrhqzvJHxbvD5wgU4AA6Av/1n+q//87c/+uNv/1nnp3xy7p+6"
    "PmP81//9n/+235f+afkzn/h9Lp/6fEaX7//w9v/+P/SF0qfmz2jHBDw4AfUffNH/+GtLMS5L8T6eWQoemz+1vMvwafhj759nfHKC"
    "Zfm7jqmfWj/j4TFzfkZ+3yu5MfNT23tPHrMWXPNdfDumFBgzk4x54Jrvt3bMu4da/SwZM/Onv8+Tmx3TFz3kpEElr/el3l8ddtB7"
    "ldY/q/KYdxXev+eW4gMNfaCS+mfCt8u9WMd9Ki/W6+d575X4gcykD5ykv7Kf5VfTwJ1T4nql9inr09fl+5reNbDrWN61LfD4TZfs"
    "veQTl+h9kylvkulNqh2THry0XOade5zpEd/2HVTX7VTzVvnnnmp9yQRvMJPbwI97q5E+z4K9Ede5m3We73GE42DHPPivq8t+mbRf"
    "3Jg+P0+H0yEbD2c8XKjSeZcHeu/67tewg+kkjCUnYcAL5OLHJBwjmzwlGnOczGZOZv28B/jdsm5Jpzu97ws87+lNKS7pK6jfv8xj"
    "F+aG0uTnJf1SQgW5tNzyVVgaPV5y/N1EZHyBacQP/KI7pc97LMtnDVmY91SvIBF0SVUkFJAz7y3toPfUvFfJ7ZFBia403ZXW5xVe"
    "uTUZ9D5yDsJFB+ntXmnU3p/LT4PwZzeILl+XkWXnldpngdhL5u3OZxp0+eIHhSlI4e0uV8qvwH1PA0g9GvQqkffs5OYFfqXzKts8"
    "O8Vhtt5COVzOLWY3IZzyePL7Vl3wYxR571Xf15hyzvhIOT3x7qUO50HGvIcSz5ATi6KGZFe8V8Fd4q80Pr3hjm66lWBK3BO9Z+/B"
    "+W1+J0X9tlAW825+53CAYHGrVH+xUXMmSVfMI434SHI7PTz5ItVYzIoUYVBjH/u9xqtwH5UzDz7c+3875n2QBfKHxrx/zw+MtQ/d"
    "UA7J7svvEuPHTdH7KAUBRxPRBU/kH/ndxu/OLbI9Er2iLqzurXd7jn7KvVfvvY/29PD1ewgroIb4dcGbjbiDNzQ0YhpeLwq5ipee"
    "sgYJcVIuTo2953tUUvVfbjD9sn13xEEOtFMOBGFRg0SRn78ddJVNf0UUNnOlehsU3+6U4ZVl0bcy/MEv3dulKOXaux5jg8gXaOLd"
    "3Kpk3BGqwWZDIZdPyPRe5X2QuKFQtHWD1n/Uqtt+snsqo/b2suYBWfOqenn8RtKgOREhqtIAnxaO295pBnHPQ7+KFjQLWAKE2tNs"
    "tsKxyiKm5Oy+u/5pwSrZlzfQ4X1BL/8SgCw0fGg9H5Djy+2W1MlUGVsogVnibwaz9BC2o0EVBMQa3z01iMJXT/iHltndJgeiOn86"
    "M29qOeeskJ/vBim6cY+0cPkZ3DJCnHt33lUg7KUR9tKrjN6l6jKE8Za3lKa1lErK8Pdc3K1eJQECP6ngGbRnnK4BhGflnEgG9/6J"
    "jT6L5o7dBpqT9Ie/kodXjZ/BmAc5KBN80Gok5vsGsLPK/HZNFq12/Wbf4gm4HhN3lm5y7pDi8wQT5V04fNBhdlx8cFTnCeaT9WlD"
    "YVKDMAFxmB85J2AYvn/zyhu/7WQq8bDJX8R9wN9us4SGeiQEn/fGI+8zRcPqMazbYZWu2N2+gk0FR31m82z4JH6rw8be8Ovd8y+s"
    "G1YvLNwMSw5D6wx17N0WrX3Se2X+OKyzwGpv5uAhlqneJq/vqn262uQE6F7gFMFnQqShaLgVsrW2NOj4PFsavH8C6Jjf7bz3VF9E"
    "PW90MU7rQ1dufn9Or/ZfUEOS9lupWVFqurP+Go6vWjXSF4DZO71RjIM3SfYdiPEa3BuoDyZ6L5rod9g3yUOa7o46Cms4o+6paY80"
    "2b5gNZRgNaBgqfakrxN9K8zRQTetCbebAdHMiGhUbhm10SLYh8XAFf5a/6DH4N07zUiDRl6Xv3+DTVgJDGesw1ZbXk/mudAjUlS2"
    "DZpLt5wiOi3QO8Cn4rHvBoXlVMSaw5UIIspJHCecgtnH32VVStZXNKYK+oe28nolVnnPfQlbA+A8SCx5vwcWbILWtMPe14fpyUuG"
    "vRsOTkz2qAK/regjMsMSuFjdsIQnN6v1CcPeic7uJGXEZws/5hUeOIbOYpkAymQ6wBeGArbPcK2RECOzWHqfMpPr0s3rUpNYf4wu"
    "oKL+MgSyPRjEp3X0nDZ6qQPl+xaBq5HY8DbUCoLy/Qs6zZxcfnfVICeH2sTvPyz3buABmdsZCJ7eEhQrvFv3Q3IYUtG0Xjqkg184"
    "DGkg72Wf4BEO9jlcGX7Nuojra3GGpUCLgefwvWNhr4uTxWNDKlQU8Gw/QZzTlGP0Uo0YOMCSyKe55dVpF/Mky4sVMqX9HsukNNVa"
    "gHOQS3Qj4nmeZuFhWIFd5SabTwfqqj0sx2Go7ouBTDgkHcMWOuM3FqqNP+4tW+KPejQSbvBkZ1XACq8fQku3NhlcVAipFE9MBE45"
    "BAvI3aVSGrEfTk30w6yPYPCBQR8/8amRPFRg8t724+YcYAtOwdh7l38lbHDAJbnvPQVHvDhIDBABPI6quulYBqv+PfAw3/JIgFHm"
    "i56CmuyP+pNRsMFj+YWD2UfcKmJXBaUX4gn1S1bnzrt1wIOY/aGBf0PRrsM6S2cvxBt/K0firhJUwciwh+SaVzDw+PD6uZg3eA9B"
    "SVHUw6yKcHmVFpzI90A5wTBJKKsdTTbFugkGa7EcHix11xiFfTqpS3B/9ku8Zj7kttU9U0jE+Mhld/EREqSi+QPQ4T29wPuoxgZ4"
    "lbuXkjDthAdFgZQDB6mrTK4DqqiFuCoi7RpMynGY+YxG9T0bTauzECB4VfFAqp59BdSKHiO4UDbmOVi6ebqVxk0CWEV2KuCbdwqK"
    "x9EneHlwxeOG7vJtBC8nxsFv49UcbsRvOypnfrZKJzD5V2j8rRzd9wTRm0YzHHDFFpZ5Ksthq58JSnMaSxYUohsCcdRpAodXjw7o"
    "JzSi5neno1ZvebxiCixCH694ZaqNkMNly1AIz7sYfehqC2eMsgWnT/NDKH7vhzDQMFcpYQh/181VCvlB9xD6Tt4JoEkJ0ES+81c5"
    "htQ9BB4txRv5q8AcjACTINJRDR6rOMRNL/jzjbvkvVHEY7CX0BjTmPNzxpyPGI7Ywt87cJ6bA4cxj4dA7vyXxhpdQUtF5/OLSsKV"
    "UGVq4KTw75bnGEZDm/+ixZvih58evCIzYBZ0e8Dmr/pk5I/1Zukrv17sIn4l+Gv6eG9Rps2mQUnCaRGzkP/I4i1wASAK8r6nyk4l"
    "BROTIZ2T4nC00EOjrlH4AMjygGLKo4j5mECsgjV8ANCG91GfCRj23vYqaEY9KJ90U9Awt0jo7CobeRDOQ/UUQBOtgaGGwOzkkeIh"
    "NSHAhGrag0vFSUbwvL/mfF6kLRa+2n4qCM85dIV6AQX+YSKnOIxQ0vew6fmdljmGXXWWaMCczbOhPvHIfqAA17AxgGqANt7+BYaI"
    "gaNoUQXRRrohWRUvkfwA+laxyImjZZFN4FwdADtqpHOBAqnGewki6vE+MHie9yn0FAGOakSA+vuJmSBK1rdfiKNX7sCBSWmkKpyU"
    "FcInEJruJp4tP3upmslZplJVnGfu2FYCW4bUhovgtMWDniyNjCM8AqHpoURCt4JuZ9oceHQjfsFt2e0+PdHQAXMGD7vv0+8dQ/hs"
    "3RoLi/aSR6JooQwkaDAIRnjrz/Z79XeXK5fitZAgSORNuewDjopL3fIk5/C9w/tSycugsPcC7wEbo1tYrpSQyxeIC++cvwhbvXbE"
    "Y/CggF0u6jtZFwxTCB194zsRAPXdVejX1IAnaJHDswCWUN/rgDMRzl11qIwZb9nTNRLeXcOMzLyJuvmd3+3AmzR77l5gnAyzovC8"
    "0fEMJxXDs/bARRsFbDEi/wQIfMTGnDO83sJe8wx7HWwCDXPtvYE/u/3K/E+LmmZYDwRJ1fhBSpEvDpxjo8j4w+FZz8QPUosU9SPI"
    "dac3CL1LwAd+6u9PYZc4r8pE29sxShgg8ZqMAb5Kr/YRgcBHHgZO3IwWFQXXqo3oZQ6w+U2QCfY8ioMejsGV27Au84mXhy9OHNQ3"
    "DtqgzZ1c2Czrwf1tXmFFMZgLwyWRAmsxcPNWWmfYIzgUb1iO2GWjl3MROYpSmmETj5+YEQNJBcdRf8/ulrnpFvzLgEAV9YI0A6M9"
    "UvEAOqsnFXRtCcqVlFI3iCWxH/BxZ+uw2dFQLkdcQrWN6BX9ve+H9SvoOm4qSM97XRtsavWCPxTbd15CQOF0zPdCQ/yh+OBdDe6S"
    "cWE/5UySThF2v/BvwVmUtkDnSGEWCGTlzDQRtP/4jsnD0TfvphvIGjSxzRbin6DiMdKisK4Q0+OIqlmOVSKfnedoABs540MrakVU"
    "6Y0ook9lBYjo8PLMmg2KZfkTu1Q80H9uCP7u2Tm2Zo5bUz2YKvkX6sggh5BCPM1OgUPTAyItYKloIBTxRT3IOimQc9cNmD+BJZfp"
    "l2a8kotmUqDy9Hs6AhxT6dx2gaibsfSRBgN72aMeghEm0gG60FPbKPJrlFUZnlPAOQqqQitF771ZTj6Xx8xiiygNXPLdeGprYnbe"
    "De/pu7NN3T38T2RN6vFmd3vYJ+CAb2NLcdqtT4TtMAz1lV6tMoL2PuuGO8jETBvJteSDZ5x5oKg9k/ie/j1LcIBztN/fMZLC621L"
    "RYbQOHfLCZU6uq6+dzARmfGESs8WHOiPSTVCU/Q0WDZHIk+lH7YwtCyKA5IWghvhQXe2oA3ACTDGDij0lTxM8vxfA8isywhUIupy"
    "p2IVZ8jV6qSPx7gIUhJeoAkGSJFFoHE0HoPMwiPjgeKE6lxLLK3sC67uWUiDIZMbQx6AjY8ycgDzinOdd+oLerMAKtiDMDooBWW5"
    "KpvJao6Fu0sfKE2e8fhAz34guGwJ/nQMBrbtn3ufd0aHcUIdJdipo/HumQfvdJW+M5kypiKMGHlvafskKmUheGM141wYylhDw/QL"
    "F4B1B6GL6wzdHWyOcsChxdEUw9oH5pKPwgAEB/SuPv6GHIXlj/bw4fPMNEIfuKvsmpb1J9Ksz8t7lQCGGZRIOii05hFadukWzHi+"
    "h9IMAAJBZ5zyhJa8mhEeiRwIiK/VmOYF+SV0ppucWvqlIO0Q8qjRM28vQoyCYe6W4t0mqeENuwuS+eYBu0EVZJOHSHEmH/vlELEa"
    "A8icfaLKBslq7NWKGS9eCI/qkznAOD7jhQyANXh6QxqKUb4d1PhLGdT+eFD9zaBo+t98RwzTdD8LdfdbjrEw3A8CX7OwrZ1JpOgS"
    "GWae8mKyYng72B/KGIEVB8iep/crs1DQ5QN8ezC04Goga/Iw+qGXTzChifwh3Ax4j0+NaubdKyJmQf6/ZsYTDvRKmo0LUQYEzj0S"
    "7ICRlaehlSI5xQPXpTEPnvEHj0VekdKHi1f3lKOnI7ADuwud4xKXuDCKY7Zew2Plj1TzuCYd3KGJ+mUzGvvnpD2/YqbjhmIQMTig"
    "5Hm85IdOyjRgo7/GaDLGvsTHDZfulBxsr0ReI4VQHX/wEGoiEcYKMVoA75JsHDcz+Sso2jyPrTX+GOv7xteWmJnL8Io4YVOOFE4k"
    "din5pM4SHC1f3HRiDlvWTEAMedUQWgPiGiDpUhTnNDxoHudsqGcYguDAiKEdeRQNVwj28xEEcXfpK/AW6jGgTB/Nw288S/ZqMPnL"
    "INpJNofz6k50/Aosfv+ACLS3fJvX5CRMvYu5Yi0DPdCs/zwhC/mvhqILR6mtm/570PDh2VxMu5/hmTiBz0CHGjBfQ56Nusbfv/Qn"
    "IDGsKdCMFwS4xtELAl8iLlCc8NDPkaXsEUdjxeoOK1I+N0FiWibQPYFLlzwjIHUPBkuxydnoGEphyFwMV2SjFArUpTho7hdE93+P"
    "LuvV/VQpxHIL04m48pipwhd1u6Ug7JO9CzsuRZIre8C2+dRC/AQfctIuEjWOP3s9OkMCMycieGJVCaZxu9HCo/3cbimQLaThXAfF"
    "XJ1rQKud5vpXQMnd7vrgJVypHlcqvxlUQ7rSFXIlT0DL65KMDCF9OL9i+6ENA74A7yVBzGLS0WCNUS851LEwriyweiHF1OGy97zB"
    "HuNjMtFJ5Qd0OIcCb3m4Z5N2tFYlOgKa4OOsovefgMnI7/MeKHgkb1s1kluPcaYi48KzHdDVkXdcBP1TOdrpmI46PyYNk3++IVvx"
    "WaL7th0xpsfxGUs7PDXv9LxQRQVpI2eM55lNnDc904hfn3ArcF2UzZSqiwnKXqZ1cUuIIC0IXD3TDrmqGJVRrkRHrVEC5Tahht4B"
    "n96EpROdLIgp1DNPRt375eFpsEwg2LJncE/DQPym7C/xzPnJd617TPLsBeKcL+PWyaL6vb+0My9LpWVmoFjDOlMsUef/4U/MysQr"
    "FoVkWXjkh+tG47yUKlciUeggWKHrrkVkEOeLcu971NX7QWQtn0soEP6VoA/8BCnN7392wMJSN4LDOgkPH9BoLuEIdeYTSWhEqFTX"
    "zDXR4H330jfxFzgtm/HCqjdTEQjjcOsRmGOEhRzG3lHhn7pQIrnMDgR4WlS94L2YBg6AVzTm5TKvxjInq3rC/lIBF1MiZi82T6Ym"
    "Hjatg+RQWeDlAbXH7Xop3GOzziJltVRbEieTV9ifMalLEj3eXoVypMVSUH5WxlcH+wVFnHo26v6vnCQ/D/qV7v/TQb+63R8Oip6U"
    "LzxOWHikfTcIdWk3ARlJ3Tt8qBBGVEdKnUwOSEEEzWdX3QCXLXpbnLZMEIGvqr4IfvqY6QDb8qM5UQ/Ldef+RaN61ywZrDDKwaJA"
    "oap+KbQ8wdpxk0DUr51SAsSBjOrn5kyJE+q3cA+cG2ade7DzkDhUEjL7UjwnGFHb5i6hNROyyDsrZrX8K8MDn82W2D2iVWAaYqOY"
    "EjXYw/CYqxEJ5XA3pO0gmMjH8KzvRz68jQeKaKf+RO3zReYRt5GveAAyvp0JO4fjhGDCor8Fol9RQuCcCxzniQhQrtBR2DmqwHvF"
    "V9dJyLohCnagB9Rn/ggwalg0ww2otEn5Ld5tOh4vhhuypgSfy3D/FnMndHKOmDfl50eK/wi+ft/JTyaX5eHHqBh+eo69ZCK4G4C6"
    "o9lolgWKVHafuTR8DGxXHlOxvF7wvE8q4ihXodJTno3I50YrRNwQBNS/MNoSwjpnMBxm12Bv8CocGrUFjZpgoT0bk1Zac9hAiA0N"
    "tUVyioRb/nrdyapqv7n6UDWmAnqyDFYDWMEdu6sNiDD6ik1Rf2RTlDN8cdWC9S/rrq/Ut7vSXwiE/Fx26caPPZTurwb9rL6vMY4v"
    "bndgITdPhSq09DjosdqGdX5kU3gslDjnOCq3bCMFiWje8VBSsQxTuYiSrGKqGjIftz5lU81Tl0HvA9aYuqm4BkAw+Se7g9Xkzxff"
    "sHpSRDtjhAS94m4U2QqaSNTINAiUESmB2uyofqSzFX+6IG4NlqavbZEosKx+8vLwc3lu1KA8STnwJCCdTbmQlGpta5C8OQZFSCYL"
    "0wNLbPbgrjBuBpCgzWfrLqTqCZEZUqAfX6+F2Zc8hRXp3jUoACrb2eQnqEBnB2AtJ3EHLVTBnkMxUO+qWyKDYvQ+Jyr91zS0R4n2"
    "nmT/YHlZdSmBKx/I1W7iOYykHmAMCTj8NDolYm8Fwi4AO6vI5pAxUNYWQurhlffjMgPHbs2W7KRVxMhOtgA8KRpfZEKy3SEdndky"
    "aRPPQwhEUEbxLsai7+KNd4rD7/AUpq/HZFp4xK7IhkqT+HlDTfvITkMqfqjxmFwiJ65pDkkqUhzSZvXF+ibg68ALyUpDKZMc4/3s"
    "ylPHOmVUHxqc6wdzWdw/Lc6a8SJcpnor9bSVOjwzBBp9QKIQc89WtIy5x2dRwqshctHYv1Whv9Jp/2tm8l8gQRyFEo94g7vScwMI"
    "LQS/xWwOgzyHsJCnLhAcgsUNdhcqqqPaUzHXasJHilMVKJAPkxlifUryu4p6QabkMQxolmj3jn2KgJMdCROVuZ1K007sR3TvqRnr"
    "WiaaCM5hZvejCKwmOOoEJ17I5o6DbsayP/4FspTgEZG0MIXOi4oSEq8ox9KTuJAy9GDAk62PhZxbzywlAnXehs4AX+WM6BrdBipR"
    "gOpXgyUMhwAsYa1KBrmlOfCxONlPtX+2NgQLhsp+fk2x60xC8MTSxB/zdvhxTnFO/hX9i3DAscgb8jjElfygOeTqsb0/16UxIbZh"
    "XS2TheqMFQ348UfQvLBSsBCS6jsw2cA7OCbdQ/kkA7VgTMobRWu0wA6HUrUxRRZwjgnNopntNNHAt9WAOYZ4nYG8HguLRjosaDaq"
    "ec56oawj6yvAEhHiq7n5Cqqtwwuv8S6Dg0Vo8NnsO4pZ+DSsh1PHNcvl4YhTjDa13RkAC8tEQ56Ak0Z9lNziuDq8anKvzmk3zkmC"
    "Cf7i4mioGkNlWLyHvhjwoQMVD/WZi5w+Z9Wqs+rtxSTE+IDLnctn7hweSaOswRFkOIu+3mw1fSp+BAobH9RNcYK7leCQad22XMAo"
    "x4hZ3TEwLdmgflCkd5UbXKheK33pev+VWf4zze8+6Hq7n10FES5ckUA0pk9WYQu1ewuxrgNZLqhvzr3PB9PZ62VQhKjmvPIjS1s1"
    "1s7m95o0czKF4VcSkbodw/JW37DkI/b7QL4sUuo07Ag5ZSEO1chq3aHJ+ikllvZA556KEOrY4p1mcmmvj2Peew5VUXocgmXuVMZc"
    "tDpq1cc4+fB4hSEDM3SmH+KLuKwPpcrsNyphCL2le+nbkPLzEENNouzmMOTBbCF9locm2w1ZrtsDZBm82tEXUBy0D7WGGbrRl2cT"
    "CV3MENQotcH5yjv6yvlm4NCvHqIsfCEFaCmftUkKcPE/ch92bDtg4gquPfNwTgBsyWoEs8p2DmqUqjIngAi7p6LAZK+d7FCxIU2L"
    "28COQAnvhM5oFM7g0wisx4+LYHFMRDQeu/jd2lVWphKdqGg/Oy/JsLF6xK0f79/FzNRqYgsthHirJNYoze+hwF04YJIALQEESoD2"
    "+Ug5IEtU9QdfBiXLMlm/GJ/CKKMbJqaRKtgsJFY7A46tMNMZaILmPUUTeoHr1D2fAStbu9JB9cw83Zlc35ndh/ZjPXqUIasXjeyl"
    "67SF8LW901EVqe2ysT5s8UPZ2ETgRWVqsxwFGkINGTbRYM2zac5RFk4qhUb6vEcO5Szrf/Uh/IrV9/Ogr670110W3wAV+0zXWv2+"
    "MDoprbh/OKNv+ywbW5puGOY1ZXRL87BFJaFDlZHBxUhc0niLGQDwb9VWqUXjPcdyiRAYR4ahMqu5tOvB73/IUqDzBm75WAgNA/zT"
    "7r15SWE1yPaqIBkp/KxD/6Imjun+vxySv8c5fzbkD4HDT0Pyr65ingXgx/HSKFg3/EC1PSN/zRZuzEM79qkazDbZo2O01uOT2Vgf"
    "mcJ59LH7bmAMfhrPdoCIoBrGRoiogGIRVuEpyI0Wub/LQZUopscFBEMit4rBs6ZlcMDE8zQlfVQhHh+N0AtwsmPdMPW5eFg4U5h3"
    "amjqZyUNSU7VE9wuhUUWxv706GGNjkutjTF3LGryMgWo3JmrqDl2HG/zZXwwcQR/WYYVpkP6MroPP4um38rHraBjhIgzxC1f4yl0"
    "ZVOe2LpAKw5r8pAsu3cKLcbCzTwV0iJ80s8KyAi5Nk9YxAnCWGNRHepQRWLldHUGMCUD6wY7QS14QvAFF4WKmgbVnVqy9YZUIpy5"
    "RaFjTUXpHRBLAEI9DVslpAUogQba2m467qhYHJy5JbNyGxrBnFNbm+27N0fMALJJLDsE3puyPY0aHhpxZm/N4w4v1I0HcaUx/jio"
    "/Djo4nCJBZhvbMALUyC7ljsYa0cnhd9dUlJPMw8mfRmKKy+Kr+9CaFJj5Kg5WB6LZJ7bMMz3rgbJYBhiXiGKZekRdLqU2g6l28G7"
    "7w5aNPMvzoI/Axd/6Cz4/2nIPwF/nEOin+UKl25DnCvmcC6tn6/CsMVJnSNiYjue+qQzscMpga7JT83HOoBmsEmAHTMCfeIi6pf5"
    "MQxMUTh3Dr/k2mDfOp+3h0mhzRYQk5oqnh7RQgEx1HcpHPiNZeTBtmF+6Oe2q7dShdQR+nBQlVmTeAhHFERmceEAyY5Q5DAvyAFq"
    "BuwAE1ESnpBx4rmVO7HDl1QekswrEqEzR8bT+rkPUDWE1IguNlpij8tzloFL3LtHq1wmIlL5MD8mpVCEl6e93eq2aS6u+lw0ndkM"
    "o2ieOs2wxqBvZ5Sfj09L1lZN3uUwGchIlvvJVsWU+k3tWTT7buNl138kF+1363wk1qYWbufR/658fCe9HlXfobP5ykf1eMyqMZq2"
    "fWKDa06ikL3Ujo6cqDurS+ICweGZnrcePliwaYd6qjJD9hM+Ls1FkzdjSIGIL8azFGvmnDVrrz4qgRo/wcP2m4BQHNSOQQ+Dlj3o"
    "0k44BxcKlcCM5donJa1p82lEFO0AHouHqqdFSsMc1WEJjthh6Voqbdlh/TbsYfy0bzr5ptFdhq0uhvpt+G1X9FJX0/caTIcSE5MF"
    "uIikoQCHL6MalPEXUOdfpvXr8Sw/+S7+ZY/7hR/FVvS/Dak/D/nds4RgkH9pKvpmcUyJ3pjpgkHUB2nEcD6RJvEn5FU4UgdUwKFQ"
    "Bf6E2Mkr01I5ECCpvuvQEKBbbcO/XZjDC9PG/yKuey6/FexK1lKiJSUV8p7+oCGHa96KVJJXHgiirRISHNDxyTWzmii0SwADE3GH"
    "ScR9hKbs3exS3TTZq5VYwkPLXbRvh6nfZ8ZnO67mXqFJufxyvOk0GR933wzWsM3G2ENQVwOoO18BGaQtTO+iAkoSdgCfVWxohzST"
    "9tm1IvQlfVEpWcFdHQ68Vq7KGlbs1aJlaTI8c26ZaWk9BMwiR+29bhnai/vdjUBk9eysTnmSyu2UQg83BW7bh8/DdcMK2yZT1sNV"
    "QcnFBvfM01eBXNLxMXUrHi5fdtrCw1CKjBP3ADXmjIM3B26n9NZKVSimmYIRp0Abr8ojMdHedw/knmg6mdzupcUrxU4+Z2pLDANd"
    "ibIXR8yXkCk4Yg7KraugXsqlQ3ShMriaTI8QAVMwPTaZ4ngRmLC4zJWvMNwv2OTuiXHdH+4QRr99vh8mlff0ptfmQRhpaqaUv3bq"
    "8kJtoWGyp01KWQWnTYgrYc7ct3Eldv14LRn0PlFYyndD/jkAI/8cevpiyD/fr3ODKb/DQxbs/CIk94c3ag76ZqxB4OtsFSr3I9Yz"
    "UB279w49mYEM4RSk77koB+RbDCWoNvQmeK8OsV75SalBg+dwaIkI5zNwj0E8Ga3Uo6wPn3qpyl4g07rEGUJRCc7ccfiNkkYU34iG"
    "dNXwsfCS0NLEdeAUa+abS9Yrz9IBHWyyqFYnjTk6DE+2zUwfHz+IIGm3MLpeTTM4Kn884zpzURNDKKdPLFlI9U80ICi44/TUDOM6"
    "yfo5gHG1MSDKDAvlQyI3d2CtLJeMWrEEtCi/C/UaMqGzhucGpq66qCv8nDZzBDFYD8l3HSnmAl4XpsV4ecu5OLolkfDt0wW0GoRR"
    "iuVm/VtnT00/U2sw9DVj6Eta7di+tUfMjtNiFTskyhA+ishT9W10t/33tSdhrZ5800NdXWgAaHOXKvUWifSrZlqoUeEDn3oc68fN"
    "QcVLjhwoV2GUK24cJawdjnm+iBVF1090mEnDQ5c30491LaF8eL5QaiuXuBxKXO0cVvWAQrGNRQrrCDsptvke7IzfgZ1fDrtCp/wl"
    "Jipx2Jk6Yyou0e/NI2m0sLdZ+y4KljrSPU25zdlYckeaBnV7ZUlNOOonP8bhdskHcIpM3t+7Ov41Q/458bt/Gn8oeIk8N3kifdnw"
    "pAG5eodDJnmjuTBYjOJo2UhJwbaGA2xeLwSwvIoUHwEnf6gtULGTUnXeg1hijYqoL0NXgJj/WYkMiI3AQd8lvxU6uLdLHnRQqmoU"
    "XxBbwDIMpBuJMvscTzX3U73fAn/XQTKKauh5qBywsdfhbF1DJ6fKYvb0AYNyp7fSNDpCdMcV2xApkV/M0ZknVx0hpIU+OwfXXsEJ"
    "idDl6wEUgzKNiUKdlYnEKaGw0Mv7KilEcZJJPRPCBYPwM1DE7Rtkek8U8vQrLqzirkLVWiRjjDKkY5kOrHgqoAT8OyuEUjLlxmoC"
    "PBYe9HXq0KtpqmcSxeT7zBPigtybJouMVv+Og5lcQUvrdBTuP+p2/3B8YMgGygEnhFInuVIHiRGkiKP9Ttj+Z5+c4MuBYG0OVypU"
    "vN/0Nq2xtdq71TAjqu/jT3jIuXIa+3cEshXKkPWcmh7iQ/0GXC6UppMu8wTg0i4xQwUq33lpKoutoYsrYXfvpTmIMIJk/gi4KLL4"
    "GZEcw05E8uWwo2H0H8OgdFztubzpOUxh0OFBOupTWif7bkfkYRB8u9vzgejBMmMpHA6qLc9bmuo0Hw16THol1lcNu/4Cg35CSvVn"
    "pPQLP8nNOfSLq5xDblG5X1zlJNrkOHUhQJUiOMFekTtAhbk7oXz6/PjC3Y1aAXjblZDG3MXvqb8d7JN8DHt2sHhW1EBnRfFkmKBI"
    "3B1fhko0EpU4GhUbvnOTPpH20s7Y7rOOTSUkTnLJtVmV/1MLv3oLn6/AA6jcl+dGoevBtPwElAF5U1Yhd1v8jKBiDEdA9ZSymU35"
    "6J3IbjFJWe5HrS+PpBgzOTj24Ovpit9CVVRcWPiBN5cHoS8hmg/qbR2w2G4CyZ2E/JlUPviWEMSGcX4TLrviJqT6GUNQ6gZ4+FE/"
    "UohlvzKGLB2uQ1ar3Oh9+/e2odoiFXVXBlGmpnZO1c1QHmrd0oODg0ZiNL6ceCKKjskjwzolvpZOQA0dIYqWRtVh/adGNpY9012R"
    "UvixRk8MQyM1RNJZWEXrnysOS0RSTnG+bNE5yDFvwQ15cHIlKeooqtYDpolpYFrSyzSOwcDXCM+EnlytYlSoSnFYRfi36igv7XNW"
    "39x9kx3l5QQFN9/I2TlFh/3QLfwIK915NgfEUOLNATGWHTY5rHRvg+lcKBE7nOQeIB+ffRDPkNedA6T9Pe0qjPgKkOGN7GWlMa3L"
    "KyDVMw0Dn7/wAk2qTSL7cTGH29Mg6yebOg0POQt93SdAM0HPHzk/zeVlAUSKhQmjv6ljUZQehwTMkX5GUV8ArWyGPCG1WXCIGXKY"
    "Oo9zGBcsWhIotxyf6aZVFKa+enLMU1n7y0MjlbcE9LJmYL+mS67Syc1QcquHL7FoJ+mRWEIPQmjYtdek8zNLNTphLP2Yqu5GPzxm"
    "dtva0olL0XlCLQZN5kcLql/Skwdmcotz4ykHcXUiD1JgHoQgIGgXoD/dexejjZodLOeuPVzGIqTgLqKMYFm4zmxjt9+kD5EmKWlq"
    "syOLJMQfgrsw/uDr6+H52QkKshTuxclZIsVmnrOtX6sc3LOlfzGI+E1bx3Y4zMjdI04sbo7tYcYGxTw5Ek+KC/F0o/sTXNdj0oF9"
    "BXeLPS4kn71ThV2YmiSLDUhjgX10JJiuZPdOKiMTENAc80KUlB72ad0FAzj4/GOetUUoWJlhV2GYZ5AH8HoxqXnSmcbZujwbWqC+"
    "0M8+XXIQ7NIUMe4b6IMHj6s4iflYTyy7BYBkGqgDPx91qm/UmDNaRBlpG8XkS2Ee7OfYDeu1Jm5e4uksosodcffofLLRyPfw5Euf"
    "xfcQ4At/iqRh929vCn/muauagkSFXs6+rn7iRAlT0yT30HNzBhuONPsI3TlozqqZM0Qw5QA6x2RUXPUIEA909UsK0NW5hI/iAntX"
    "SIe4ppgenfdEMcwlmyY7jTube28bdXtcxuy5e41aoqLPCtUEg3nA81ifEMwEVY/zCKzZAjXUh6dGKqi4k7bEIvXtPSDJlboZ1N8k"
    "EPvYP6wiiyh8gdU4TDxpcnMdt3G4XkvMmfbFYjkBifVQPuxqbMM3NPcTagrix0U5PA9zoesheJg6Rwxc19wayhhOlNO7MWLluFHs"
    "mps3QIW3oho4DvNNZWw0WWUM8jgIMzFcIeBxpiNyUrGBiZxhYd94Ix6rxNEAaoPqOEbslpDQCvtK7OtQ4xt5BqJ+RDjZdf5bO27h"
    "S9iLJyVgevqY+APBtydsl7TzejrbJ8EBdss6Q262K2zDZXsU1kFar70Op9BJUItq7fl44UNOFG0Xy8GX0EptoU9ESdULKS0eGmcq"
    "D6MuknRhf+bKfgA5u+mim2MR+asCB1ZsM76KRmUsW1iPukN6UkrWu0u+QCQGlhQkQ8aG9O7UvecJ0YOGZtF35eWfACvte1mosYyH"
    "Jb5DHsKSFsKlWIx+mAiO0JGP8jmxI125MHYRYVimy60rDZ5z1QJQ1SmFckVYkg0sOQ0eFKqx6Rn1O5XHlnM7c3s2meNbiKAuhmSv"
    "dihP7gKrNZKofW2JmUKdIp5ZVezkIq5OZzwT314FLGZT11g+tFEf3902qGCJj0hGotKxNhEuVIHZKlfVXWaB7bGLTKPCCG3qfZ3X"
    "bzX6xZeTr9nrt8DYN36m49nOcj2O+HPFLlcsekFC+sTfXu3EVVcwJ/2yxeSiVPseGNhwfWQcDQ2uJuJH+gga977TvUEFqnyxLfRh"
    "fUwZoefCQaXWdHmvJ7k7DoMbUG0xTltCDkedZMwwzoYXQylKvnpZCd6IccQQMKTEbX3V7I4NQ5HuWz5aTgwyNwMFYVLtWM1c78wf"
    "CbjKODbQiUA+B68ETZBnYZKKExDvH7a1TDmelsMxhi3RQyV/jw0Ia0SiNbF8DHgL7W2Zc6L2b5OP02nykdRp7NF2zJupFVkar6O3"
    "iR7up6z1ZPKttZ5SfiXIRr0Vl58cbKSj2AwUxaVno2YTUImh2BzyMV0b8AoB2UqHWS1aUc8CKtiJMn+0HxTii37Y/ovwhA3BPEHJ"
    "aiJS3QcrRoXgNtW6ajLRYU588R3IMOGcdCKLikSlnb2Kyfw+3lapVfizjy08hW8/nFwCEzgPyIEUAYrNpJfueE7kw+LZ2B4gn9ho"
    "8aijkvOFrJK4uI1t4Poc0bKHqyAb7YeFWH1Bk0XlytUnUjqZas8Zi8nWJ5JZQv/gExHMcpaNc0hG1JzXal/yOM54h0MyqqnDpKEl"
    "9qgeEv0dufZQGr3uSSPd4QdhDdFNzYZkxLPxM4EilSRgH/uEvcH2g0YPoDOcNzK2XtQ8E6rJ6pGOqFSTkzmOxLcNWGQHZt4i53xa"
    "enBin7N3kyFKmAYl4JOmIAVNVElAH++4eeKhFIFOj1viKcx1Uu+LBLtiBQJcOS0Vgl6bFpqvY5+sZjJ4xtnlGjRnMhQzkJ3YxcDt"
    "aDBnDbtWCpr4qmcYWFWdUXnufb89zJptHy3ZBrYHtrj3cQ0MFuRtwi2sSOZ9uaChsGC/2jokgwK9qSSGBxK8WFRi14GSzExwUZyY"
    "GeEUJxTNLUoVIFMeDVGrpLFQn4bR1XqPpdy3xTj6UeGXGSOSmnLGa0jxZxOOYY5JgAu7g5zwMryXB3xOwn5BEoQ3/iHDfBq/Pr5N"
    "bAhFUOExUGHX7Ysgs5btZYX3Tj7Y4psdYAshX6mXap4IS61j1VpPXU2Ye69Si2BZ6HUwydJe++ij+vGdqbh3lyqWcqaLwPFzevM6"
    "CGJiWEGEsUuCB1yHFn8MZS5ZO88AgGy70/31lnemmD52xPVQDiT0kVM4vo2KQNQrh1oC0NrXjlmDYIIbtHBv7mqM8Esj+jGUyiHr"
    "xMVa4mJiWo+IVFi3E0twj5eqftqKACfAEpK5u+V55qCvL42CqMCY5eSqroFov6MFrvxIdARcdIL83jiGXRmrpyn9SzRxsEKjjUxp"
    "Ltl4kjabNIDzYtjQi3ikuUVPsKMsFfKsX+By2aeghNYg+F3bHLayLMFpY5u0sQ3cd8Z6+tQZxuRuIL8rgJ+a9o1AetYQOkZV+mxg"
    "LUFP904VU+rV9/8+FgZKfcIJpidoVcdRyHPp3qriNlek9azTgUipLdpsgKnk7okBLtlsp4UBTP/mWFqsbwi/MNfQ7UaW3Daklg4H"
    "LGt4bZN+KbHGYXLTJ4wyUWInFiMa73U4UuHSX7IF6dz54IixYGVVK5cZS3HXO8tX62vcu/Map/fJVOXZk8LqZ0FdioY4n+4kWpE7"
    "sr6Z4PYWuADE8u3zEmcK+2CcVqeT7UaNlUKH6Y1bxCp/GHQ4uMe1ZGhMXUf9/kaUVXGMoDPG+yIac0+aLOQTWYcJyY57mnHT+MoG"
    "MzNJUtZ/Up13H/evZNbPvUkuGr2QWa9eeKZS+KWvJA2sMHtu+jpdCpfd/viF5pY/+MoPHW5Zaurr67nbNaTNtjOPZTWaAnnb94BS"
    "jqyb3OKquum8+cCNFKw3SCgWl9ZAhMYesUdGSNGZ1EZAl2kimzgwL6S356P3oxTlEs1KdJKqNQyyDR7z8U7vzBF/JVZ0EiGX0EQz"
    "tiB8jZ59Xwf+8D9/rdDdMPUXHAr9FyXRgtX7BR2SYhom2Ybd2yGE0ZArljdJ4PYGGMo1hYbXvKl9cPeZCrAN3UEhMJg8w6hinsQ8"
    "+DGmFwFWJqjeg4rddtdHq5ugUMhx4+ThmtdK1C1QdhK1HtB9OrmzhdvMyReRZveYlzm1UH/rLbZjAEczR6spw0GmnXe0dskaEFG5"
    "2Pr04Vr5qJf44U8Py0Iqzd70SLw0lMl9GE/dRKWsTP4HFVw9CoRWCSVLYY2zE4t8xQOeMzWxUrvgvRU2P+/6gjr19ZJk4Nu8Ddz2"
    "wX3VpY0Lo6GzBD13pOV9wBkjvsGY0D3b3gf08VVOpBiH8DTnkcPRJpcElXtBuklIWKGkDHpaNKvcUVqYnzKsw/joZUPWqDqDWQB7"
    "pTB8HS7VJFG9uEC9/Bw0rtNBYPJHR3rDpoHLuCIBEaheVYmEnOkbpfAfVLrReqb7jHDwWnPlzWJVQAwZDGMZwzmI+ekCUjTZc90m"
    "nwMSanHJL7krJb9CNxMbvgTYuo31yiQEd6VFTFGNmsxJD+V1CzfpVFI2MGBm8P2Rj7Ju+EmavIeif9R2jRxyRiU/h+YW/2myV1vx"
    "aqq/VHN36gTr4+1qYzuP/Rlg1si5VY+Rz/ZFLsah4M/aXe160+dWMOygToJSGDYvbudJOABL4S3NMvoiTNBoN2jMAT3wT3hRNHF3"
    "dgASUNH17e3gSRE7GZTpWUOkqthIFca4AXl6BcDOMY1CPzb3yZhU2dDMM9e4zZ7d17xXmOsRBh2+MElatg6XCTg7jCVz1LS3iI9V"
    "FWbaGduCmnk4bUJVBKT5+DybwtN/Yp1nYuFZFZBtOJtI+SExrtMz7oLeEsV1ypG6xpn60pwy6rZIY7whxSEx/ufzVHbJKrMcOGnO"
    "eu3Evd+qP/u+7WdG4PTK8d2e8J80i8FGtL4AA9bj2lunoe7z9IVJ0VFZoucSCB3kctTdxc7M4OFszJP38DBIVjFBRfdNMix9ba/q"
    "/Md53o1N+v4XxuY/rAYvCrGeCpG7vtvHjsHr0Wh21Z03zrO8uqfF9eLqTKnNSAxAY30eW3Uu+vL7QR2LLahq1V8KyzYJTm4T9WDh"
    "gSDBgGL0cfsilYt7f2vXvMXyIxLx0C8klXfFyRvSjyiWGAxeNMx8VdOH1Z/NdJwxF5ioTm0T7OmHdQ2bF6OaKvGlcve6WpSw5ps8"
    "RG8bR3TdK2EJwt9LhTu1iVDgeyv77jafMVZ/pxM+9C9qZWMf2BSbyMqk7+mlZIYYmKXC0dY2jGeoiHbZOVWQx+Uv83ykW4EK/OkD"
    "fb4LuTa58jn8j7fhqPEEbhR3qmPfp2tDJwh57Yo9JMB8T3JMJTMN7sCfHOpGdgwkyVNT8yHP4Ve1pfHJyh9fYC9xwpZxhdHn7F9h"
    "1BSk8RdvyXV0KYh11anb9vQv3oqWskSHZEgYgMu/EzINFRik+2FLmIRzAeXemChkA4im4l5QQQl1F+lEXk+J6iyackyu8hUhi9dB"
    "ZN0cBlhBrtyXAcr/ZW30lXJaVmHyDGMd041t5umXiVoeeFMxkrwe0g7KSFmX5gFAScpGyUPJxSf6bVQ5eL9Ujpy8Z1m7r9CgHtYc"
    "2dca6hzk041uMMyJ0cJbYFKWAJC3/9QgndVD1IFGubBp4+oSMZsf6Sre8nuirYaqqJtKNHL5Hilk6JexChEVqefvEFN310Ul2dyj"
    "QpQX7daORPXqn40KEO1igVstR/XKRCzzCgfVHQD1yOZNE1fTD50AFjVIMaA1YiRwIWK1a9mHg2soeTsFXVCmkDvJ/CP0A0x4/PQt"
    "oi59j0bR+jCsVhqLdd9wsHFTI/XXSQG6GN/0NDHsU4RR9mCL7WgaYpHTGwn4DTO6Tab5rQUUbX/FZ5w05HJ2M+kcNigwPO2oLwOT"
    "krTPwdVaoPiXOoZAJEfWpLjYkjUWTkcZEyKVkJvO0vfgCXEgl4W5t/4FQhvkMW7hK0cV85bG/JrH+u+S91+J/3nXVRBviNyBnsj+"
    "sp1WQ5U/9MjZcBiH4mKKsTNaaI95wnfM9+nrspxzOXaLJhJ53UFsXesOvKgFJH0bX+zFZ4guN4DkRQU+BwR9flFmu1/P6jVEl5iK"
    "qlbS5NylQ443E45eVLbPE3jVrWc8yRjuc+qqFq7nqmeNemB4dZWo2MNOaJuU5ORNvFIJycgiF+tx5oPNfLa23fUt0NXENaJhiDao"
    "1Pkhlk0xiAfrjTqVAi8yd8B5oJfD1/XEGI9x5Q58Giey56DMhi2vYYTzoHR0FslbQyhmeCQ4kGDuVusQVOhv2gWthTTmV6GSMDNl"
    "vpD0koIwc0R8KoAVah2IFDQrNSPaa4j2qjnV64tw/U0OElnuH0G1/wbx961IRJElpqZHyjtocSgCrz4XiTSZ0wfmaETV/9hmynlY"
    "SbxdQNVoPjGKo6kzjKlTml2PjZ/jVgl8WOV2qG5EgOPBw/KtXDJ1nPTm2RqeIyIVQ2M5Xkzf1EHj4trLnQJW8tDkMjuqwy9D/HpO"
    "xiVYyd2wn8Rh6B4HQ4X7cUDYhKONmu0xFg/14vQVejQXxmi/FdeieqWV0XI6+lA/9pnT8qE7A23Nkfdndd5CgMN//684Vv/aQ/xn"
    "J77dpzfnL76vVGrlNu3LiELj1IDrPPH7d7/B9+VfuRy//eP/AYP5LXc="
)

# Terminal emulators we know how to drive, best-first. The list value is the
# argv prefix that means "run the following command".
TERMINALS = [
    ("kitty", []),
    ("foot", []),
    ("alacritty", ["-e"]),
    ("ghostty", ["-e"]),
    ("wezterm", ["start", "--"]),
    ("konsole", ["-e"]),
    ("gnome-terminal", ["--"]),
    ("xterm", ["-e"]),
]


def art_bytes() -> bytes:
    """The terminal-ready ANSI art as raw bytes."""
    return zlib.decompress(base64.b64decode(ART_B64))


# --------------------------------------------------------------------------
# locate the graphical session on the physical display
# --------------------------------------------------------------------------
def _loginctl(*args) -> str:
    return subprocess.check_output(["loginctl", *args], text=True)


def _session_props(sid: str) -> dict:
    props = {}
    try:
        out = _loginctl("show-session", sid,
                        "-p", "Type", "-p", "Display", "-p", "User",
                        "-p", "Active", "-p", "TTY")
    except subprocess.CalledProcessError:
        return props
    for line in out.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            props[k] = v
    return props


def resolve_session(username: str | None):
    """Return the session dict for the target display, or None.

    Default target is whatever session is currently active on seat0 (i.e. the
    person sitting at the monitor). If *username* is given, pick that user's
    graphical session instead, preferring an active one.
    """
    if not shutil.which("loginctl"):
        return None

    candidates = []
    if username:
        try:
            listing = _loginctl("list-sessions", "--no-legend")
        except subprocess.CalledProcessError:
            return None
        for line in listing.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[2] == username:
                candidates.append(parts[0])
    else:
        try:
            active = _loginctl("show-seat", "seat0",
                               "-p", "ActiveSession", "--value").strip()
        except subprocess.CalledProcessError:
            return None
        if active:
            candidates.append(active)

    best = None
    for sid in candidates:
        p = _session_props(sid)
        if p.get("Type") not in ("wayland", "x11"):
            continue
        info = {
            "sid": sid,
            "type": p["Type"],
            "display": p.get("Display", ""),
            "uid": int(p.get("User", os.getuid())),
            "tty": p.get("TTY", ""),
            "runtime": f"/run/user/{p.get('User', os.getuid())}",
        }
        if p.get("Active") == "yes":
            return info  # active session wins outright
        best = best or info
    return best


def find_wayland_display(runtime_dir: str) -> str:
    socks = sorted(
        s for s in glob.glob(os.path.join(runtime_dir, "wayland-*"))
        if not s.endswith(".lock")
    )
    return os.path.basename(socks[0]) if socks else "wayland-0"


# --------------------------------------------------------------------------
# build the environment / privilege drop for the target user
# --------------------------------------------------------------------------
def build_env(pw, sess) -> dict:
    runtime = sess["runtime"]
    env = {
        "XDG_RUNTIME_DIR": runtime,
        "HOME": pw.pw_dir,
        "USER": pw.pw_name,
        "LOGNAME": pw.pw_name,
        "SHELL": pw.pw_shell,
        "PATH": "/usr/local/sbin:/usr/local/bin:/usr/bin:/bin",
        "DBUS_SESSION_BUS_ADDRESS": f"unix:path={runtime}/bus",
        "XDG_SESSION_TYPE": sess["type"],
        "TERM": "xterm-256color",
    }
    if sess["type"] == "wayland":
        env["WAYLAND_DISPLAY"] = find_wayland_display(runtime)
        if sess["display"]:  # Xwayland also up
            env["DISPLAY"] = sess["display"]
    else:
        env["DISPLAY"] = sess["display"] or ":0"
        xauth = os.path.join(pw.pw_dir, ".Xauthority")
        if os.path.exists(xauth):
            env["XAUTHORITY"] = xauth
    return env


def make_demoter(pw):
    """preexec_fn that switches the child to the target user (root only)."""
    uid, gid, name = pw.pw_uid, pw.pw_gid, pw.pw_name

    def preexec():
        os.initgroups(name, gid)
        os.setgid(gid)
        os.setuid(uid)
        os.chdir(pw.pw_dir)

    return preexec


def payload_command() -> list:
    """A self-contained `sh -c ...` that paints the art then holds the window
    open — no shell, no interaction. Closing the window (WM) ends it.

    The art is embedded as base64 so it survives shell quoting intact.
    """
    b64 = base64.b64encode(art_bytes()).decode()
    inner = (f"printf %s '{b64}' | base64 -d; "
             f"exec sleep 2147483647")
    return ["sh", "-c", inner]


# --------------------------------------------------------------------------
# projection
# --------------------------------------------------------------------------
def project(sess) -> dict:
    try:
        pw = pwd.getpwuid(sess["uid"])
    except KeyError:
        return {"status": "error", "reason": f"no passwd entry for uid {sess['uid']}"}

    env = build_env(pw, sess)
    demote = os.geteuid() == 0 and sess["uid"] != 0
    if os.geteuid() != 0 and sess["uid"] != os.getuid():
        return {"status": "error",
                "reason": "cross-user projection needs root"}

    preexec = make_demoter(pw) if demote else None
    payload = payload_command()
    target = env.get("WAYLAND_DISPLAY") or env.get("DISPLAY")

    for term, prefix in TERMINALS:
        exe = shutil.which(term, path=env["PATH"])
        if not exe:
            continue
        try:
            subprocess.Popen(
                [exe, *prefix, *payload], env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                preexec_fn=preexec,
            )
        except OSError:
            continue
        return {"status": "launched", "user": pw.pw_name,
                "session": sess["type"], "display": target,
                "terminal": term, "demoted": demote}

    return {"status": "error", "reason": "no usable terminal emulator found"}


def write_to_text_console(sess) -> dict:
    """Fallback: monitor is on a text VT (no desktop). Write art to it."""
    tty = sess.get("tty") if sess else ""
    if not tty:
        return {"status": "error", "reason": "no text console found"}
    dev = f"/dev/{tty}"
    try:
        with open(dev, "wb") as f:
            f.write(b"\n" + art_bytes() + b"\n")
        return {"status": "console", "device": dev}
    except OSError as e:
        return {"status": "error", "reason": f"cannot write {dev}: {e}"}


def _run() -> dict:
    sess = resolve_session(os.environ.get("BEAR_USER"))
    if sess is None:
        return {"status": "error", "reason": "no active graphical session on seat0"}
    result = project(sess)
    if result.get("status") == "error" and sess.get("tty"):
        console = write_to_text_console(sess)
        if console.get("status") == "console":
            return console
    return result


# main() is memoised: the runner exec()s the module body AND calls main(),
# so without this the bear would launch twice.
_RESULT = None


def main():
    global _RESULT
    if _RESULT is None:
        _RESULT = _run()
    return _RESULT


if __name__ == "__main__":
    print(main())
