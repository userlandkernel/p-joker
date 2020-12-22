import os
import sys
import platform
import struct
import json
import ast
import getopt
from kernel.kernel import KernelMachO
from iokit_kextclass.kext_analyzer import *
from lib.lzfse import *
import lzfse



class joker(object):
    pass

class CommonTool(object):

    @staticmethod
    def read_file(file_name, start=0, step=1):
        content = []
        with file(file_name, 'r') as f:
            lines = f.readlines()
            for i in range(start, len(lines), step):
                content.append(lines[i].strip())
        f.close()
        return content

    @staticmethod
    def save_file(filename, xmlstr=""):
        try:
            with file(filename, 'w') as f:
                f.write(xmlstr)
            f.close()
            return True
        except Exception as e:
            return False

    @staticmethod
    def save_jsonfile(filename, jsonobject={}):
        try:
            with file(filename, 'w') as f:
                f.write(json.dumps(jsonobject))
            f.close()
            return True
        except Exception as e:
            return False

    @staticmethod
    def read_jsonfile(sfilename):
        func_dict = json.load(file(sfilename))
        return func_dict

def Usage():
    print(" Usage: python p-joker.py kernelcache -hkls [-Ke bundleID(or list)] [-d dir]")
    print("\t -h, --help")
    print("\t -k, --kext_list: list all the kext informations")
    print("\t -K, --kextdump kext_bundle_identifier: dump this kext")
    print("\t -d, --dir dumpdir: set the output dir")
    print("\t -l, --lzss: decrypted the kernelcache")
    print("\t -e, --extract: extract all meta classes and their methods for given extension bundleID (Note: you'd better use this feature on Linux)\n\n")
    print(" For example:")
    print("\t decrypt kernelcache, support bvx and complzss format:")
    print("\t\t $ python p-joker.py kernelcache.encrypted -l\n")
    print("\t list all the kexts info:")
    print("\t\t $ python p-joker.py kernelcache.decrypted -k\n")
    print("\t dump certain kext from kernelcache:")
    print("\t\t $ python p-joker.py kernelcache.decrypted -K com.apple.iokit.IOHIDFamily\n")
    print("\t extract all meta class and their functions information for all extensions within kernelcache:")
    print("\t\t $ python p-joker.py kernelcache.decrypted -e " + '"[' + "'all'" + ']"\n')
    print("\t extract all meta class and their functions information for certain extensions within kernelcache:")
    print("\t\t $ python p-joker.py kernelcache.decrypted -e " + '"[' + "'com.apple.iokit.IOHIDFamily'" + ']"\n')


def print_kext_list(kext_prelink, kext_notprelink):
    print("\t%-20s%-100s" % ("offset", "Driver Name(Driver BundleID)"))
    for driver in kext_prelink:
        for addr, details in driver.iteritems():
            driver_bundleID = details[1]
            driver_name = details[0]
            #print("\t%-20s%-100s" % (addr, driver_name + " (" + driver_bundleID + ")")
            print("\t%-20s\t%-100s" % (addr, driver_name + " (" + driver_bundleID + ")"))
    for driver in kext_notprelink:
        for addr, details in driver.iteritems():
            driver_bundleID = details[1]
            driver_name = details[0]
            #print("\t%-20s%-100s" % (addr, driver_name + " (" + driver_bundleID + ")")
            print("\t%-20s\t%-100s" % (addr, driver_name + " (" + driver_bundleID + ")"))


def decrypt_kernelcache(filename, output_dir):
    magic, img_type, version, size, compress_mode, data = get_image_info(filename)
    dec_kernel_f = "kernelcache.decrypted"
    dec_kernel = os.getcwd() + os.sep + dec_kernel_f
    if output_dir:
        dec_kernel = output_dir + os.sep + dec_kernel_f

    if compress_mode == "complzss":
        decrypt_kernelcache_v1(filename, dec_kernel)
    else:
        decrypt_kernelcache_v2(data, dec_kernel)


def decrypt_kernelcache_v1(filename, dec_kernel):
    offset = 0
    with file(filename, "rb") as kernel:
        kernel.seek(0, 2)
        size = kernel.tell()
        kernel.seek(0)
        while offset < size:
            data = struct.unpack(">L", kernel.read(4))[0]
            if hex(data).replace("0x", "") == "cffaedfe":
                offset -= 1
                break
            offset += 1
            kernel.seek(offset)
    if os.name == "posix":
        cmd = "./lib/lzssdec_mac -o 0x%x < %s > %s" % (offset, filename, dec_kernel)
    else:
        cmd = "./lib/lzssdec_elf -o 0x%x < %s > %s" % (offset, filename, dec_kernel)
    os.system(cmd)
    print("kernelcache is decrypted into file %s" % dec_kernel)


def decrypt_kernelcache_v2(data, dec_kernel):
    decompress_data = lzfse.decompress(data)
    with open(dec_kernel, 'w') as f:
        f.write(decompress_data)
    print("kernelcache is decrypted into file %s" % dec_kernel)


def list_services(kernel_f):
    cmd = "strings %s | grep 'UserClient$' > .services.txt" % kernel_f
    os.system(cmd)
    services_list = []
    with file(".services.txt", 'r') as se_handler:
        services = se_handler.readlines()
        for s in services:
            if 'A' <= s[0] <= 'Z':
                se_name = s.strip('\n').replace("UserClient", "")
                if len(se_name) < 3:
                    continue
                elif se_name in ["Release", "Detach"]:
                    continue

                services_list.append(se_name)
        se_handler.close()
    os.remove(".services.txt")
    print("\t--%-22s--" % "service names")
    for service in services_list:
        print("\t%-20s" % service)
    #print(services_list
    print("total is: %d" % len(services_list))



if __name__ == '__main__':
    if len(sys.argv) < 2:
        Usage()
        exit(0)
    kernel_f = sys.argv[1]
    is_printK = False
    is_dumpK = False
    is_dec = False
    is_list_services = False
    dump_driver = ""
    dump_dir = ""
    extract_sub_ioservice=""
    if not os.path.exists(kernel_f):
        print("file %s not found!" % kernel_f)
        exit(0)

    try:
        options, args = getopt.getopt(sys.argv[2:], "hklsK:d:e:", ["help", "kext_list", "services", "Kext_dump=", "dir=", "lzss", "extract="])
    except getopt.GetoptError:
        exit(0)

    if not len(options):
        Usage()
        exit(0)

    for name, value in options:
        if name in ("-h", "--help"):
            Usage()
            exit(0)
        elif name in ("-k", "--kext_list"):
            is_printK = True
        elif name in ("-K", "--Kext_dump"):
            is_dumpK = True
            dump_driver = value
        elif name in ("-d", "--dir"):
            if value[-1] == os.sep:
                value = value[:-1]
            dump_dir = value
        elif name in ("-l", "--lzss"):
            is_dec = True
        elif name in ("-s", "--services"):
            is_list_services = True
        elif name in ("-e", "--extract"):
            extract_sub_ioservice = value
        else:
            exit(0)

    if extract_sub_ioservice:
        if extract_sub_ioservice == "all":
            pass
        else:
            sub_ioservice_str = extract_sub_ioservice
            sub_ioservice = ast.literal_eval(sub_ioservice_str)
            getSubIOServicesClass(kernel_f, sub_ioservice)

        exit(0)

    if is_list_services:
        list_services(kernel_f)
        exit(0)

    if is_dec:
        decrypt_kernelcache(kernel_f, dump_dir)
        exit(0)

    kernel = KernelMachO(kernel_f)
    driver_list_prelink, driver_list_notprelink = kernel.get_driver_list_v1()

    if is_printK:
        print_kext_list(driver_list_prelink, driver_list_notprelink)

    if is_dumpK:
        if dump_driver == "all":
            for driver in driver_list_prelink:
                for addr, details in driver.iteritems():
                    driver_name = details[0]
                    driver_bundleID = details[1]
                    if "Pseudoextension" in driver_name:
                        print("kext %s is only a pseudo extension!" % driver_name)
                        continue
                    kernel.extract_kext(driver_bundleID, dir=dump_dir)
        elif dump_driver:
            isfound = False
            for driver in driver_list_prelink:
                for addr, details in driver.iteritems():
                    driver_name = details[0]
                    driver_bundleID = details[1]
                    if dump_driver == driver_bundleID:
                        isfound = True
                        if "Pseudoextension" in driver_name:
                            print("kext %s is only a pseudo extension!" % driver_name)
                            continue
                        else:
                            kernel.extract_kext(driver_bundleID, dir=dump_dir)
                            if dump_dir:
                                print("kext %s is dumped in %s!" % (driver_bundleID, dump_dir))
                            else:
                                print("kext %s is dumped in %s!" % (driver_bundleID, os.getcwd()))
            for driver in driver_list_notprelink:
                for addr, details in driver.iteritems():
                    driver_name = details[0]
                    driver_bundleID = details[1]
                    if dump_driver == driver_bundleID:
                        isfound = True
                        print("kext %s is not prelinked in kernelcache!" % driver_name)
            if not isfound:
                print("kext %s is not found in this kernelcache!" % dump_driver)
